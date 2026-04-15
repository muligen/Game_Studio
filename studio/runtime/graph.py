from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from studio.artifacts.registry import ArtifactRegistry
from studio.domain.requirement_flow import transition_requirement
from studio.memory.store import MemoryStore
from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.dispatcher import RuntimeDispatcher
from studio.runtime.llm_logs import LlmRunLogger
from studio.schemas.design_doc import DesignDoc
from studio.schemas.runtime import PlanState, RuntimeState
from studio.storage.workspace import StudioWorkspace


def _merge_telemetry(
    current: dict[str, Any], *, status: str | None = None, node_name: str | None = None, trace: dict[str, Any] | None = None
) -> dict[str, Any]:
    merged = dict(current)
    node_traces = dict(merged.get("node_traces", {}))
    if node_name is not None and trace is not None:
        node_traces[node_name] = trace
    if node_traces:
        merged["node_traces"] = node_traces
    if status is not None:
        merged["status"] = status
    return merged


def _merge_runtime_state(
    runtime_state: RuntimeState,
    *,
    state_patch: dict[str, Any],
    node_name: str,
    trace: dict[str, Any],
    status: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> RuntimeState:
    patch = dict(state_patch)
    overrides = dict(overrides or {})
    plan_in = patch.pop("plan", None)
    telemetry_in = patch.pop("telemetry", None)

    telemetry_current = runtime_state.telemetry
    if isinstance(telemetry_in, dict):
        telemetry_current = {**telemetry_current, **telemetry_in}

    update: dict[str, Any] = {
        **patch,
        **overrides,
        "telemetry": _merge_telemetry(
            telemetry_current,
            status=status,
            node_name=node_name,
            trace=trace,
        ),
    }
    if isinstance(plan_in, dict):
        update["plan"] = PlanState.model_validate(
            {**runtime_state.plan.model_dump(mode="json"), **plan_in}
        )

    payload = runtime_state.model_dump(mode="json")
    normalized_update: dict[str, Any] = {}
    for key, value in update.items():
        if isinstance(value, PlanState):
            normalized_update[key] = value.model_dump(mode="json")
        else:
            normalized_update[key] = value
    payload.update(normalized_update)
    return RuntimeState.model_validate(payload)


def _require_state_str(state: dict[str, object], key: str) -> str:
    value = state.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value


def _new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:10]}"


def _session_tag_for_run(run_id: str) -> str:
    prefix = "run-"
    if run_id.startswith(prefix):
        return run_id[len(prefix):]
    return run_id


def _consume_agent_llm_log(agent: object) -> dict[str, object] | None:
    consume = getattr(agent, "consume_llm_log_entry", None)
    if not callable(consume):
        return None
    entry = consume()
    if not isinstance(entry, dict):
        return None
    return entry


def build_demo_runtime(root: Path, force_review_retry: bool = False):
    """Each invoke gets a unique run context so the same compiled graph can be reused safely."""
    dispatcher = RuntimeDispatcher()
    artifact_registry = ArtifactRegistry(root / "artifacts")
    memory_store = MemoryStore(root / "memory")
    checkpoints = CheckpointManager(root / "checkpoints")
    llm_logs = LlmRunLogger(root / "logs")

    def _checkpoint_key(run_id: str, node_name: str) -> str:
        return f"{run_id}-{node_name}"

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        run_id = _new_run_id()
        runtime_state = RuntimeState(
            project_id="demo-project",
            run_id=run_id,
            task_id=f"{run_id}-planner",
            goal=state,
        )
        result = dispatcher.get("planner").run(runtime_state)
        merged = _merge_runtime_state(
            runtime_state,
            state_patch=result.state_patch,
            node_name="planner",
            trace=result.trace,
        )
        checkpoints.save(_checkpoint_key(run_id, "planner"), merged)
        return merged.model_dump(mode="json")

    def worker_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        run_id = runtime_state.run_id
        session_tag = _session_tag_for_run(run_id)
        runtime_state = runtime_state.model_copy(update={"task_id": f"{run_id}-worker"})
        agent = dispatcher.get("worker")
        result = agent.run(runtime_state)
        llm_entry = _consume_agent_llm_log(agent)
        if llm_entry is not None:
            llm_logs.append(run_id=run_id, node_name="worker", **llm_entry)
        stored = []
        for artifact in result.artifacts:
            unique_id = f"{artifact.artifact_id}-{session_tag}"
            to_store = artifact.model_copy(update={"artifact_id": unique_id})
            stored.append(artifact_registry.save(to_store))
        memory_key = f"{run_id}-summary"
        memory_store.put("run", memory_key, {"summary": "worker produced concept draft"})
        merged = _merge_runtime_state(
            runtime_state,
            state_patch=result.state_patch,
            node_name="worker",
            trace=result.trace,
            overrides={
                "artifacts": stored,
            },
        )
        checkpoints.save(_checkpoint_key(run_id, "worker"), merged)
        return merged.model_dump(mode="json")

    def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        run_id = runtime_state.run_id
        runtime_state = runtime_state.model_copy(update={"task_id": f"{run_id}-reviewer"})
        if not runtime_state.artifacts:
            updated = _merge_runtime_state(
                runtime_state,
                state_patch={"plan": {"current_node": "reviewer"}},
                node_name="reviewer",
                trace={"node": "reviewer", "reason": "missing_artifact"},
                status="needs_attention",
                overrides={"risks": [*runtime_state.risks, "missing review artifact"]},
            )
            checkpoints.save(_checkpoint_key(run_id, "reviewer"), updated)
            return updated.model_dump(mode="json")

        payload = {} if force_review_retry else dict(runtime_state.artifacts[0].payload)
        agent = dispatcher.get("reviewer")
        result = agent.run(runtime_state, artifact_payload=payload)
        llm_entry = _consume_agent_llm_log(agent)
        if llm_entry is not None:
            llm_logs.append(run_id=run_id, node_name="reviewer", **llm_entry)
        risks = list(runtime_state.risks)
        patch_risks = result.state_patch.get("risks")
        if isinstance(patch_risks, list):
            risks.extend(str(item) for item in patch_risks)
        if result.decision.value == "retry":
            risks.append("review retry requested")
        status = "needs_attention" if risks else "completed"
        updated = _merge_runtime_state(
            runtime_state,
            state_patch=result.state_patch,
            node_name="reviewer",
            trace=result.trace,
            status=status,
            overrides={"risks": risks},
        )
        checkpoints.save(_checkpoint_key(run_id, "reviewer"), updated)
        return updated.model_dump(mode="json")

    graph = StateGraph(dict)
    graph.add_node("planner", planner_node)
    graph.add_node("worker", worker_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile()


def build_design_graph():
    graph = StateGraph(dict)

    def design_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        requirement_id = _require_state_str(state, "requirement_id")
        workspace = StudioWorkspace(Path(workspace_root))
        workspace.ensure_layout()
        requirement = workspace.requirements.get(requirement_id)
        designing = transition_requirement(requirement, "designing")
        pending_review = transition_requirement(designing, "pending_user_review")
        design_doc = DesignDoc(
            id=f"design_{requirement.id.split('_')[-1]}",
            requirement_id=requirement.id,
            title=f"{requirement.title} Design",
            summary=requirement.title,
            core_rules=["rule 1"],
            acceptance_criteria=["criterion 1"],
            open_questions=["question 1"],
            status="pending_user_review",
        )
        workspace.design_docs.save(design_doc)
        workspace.requirements.save(
            pending_review.model_copy(update={"design_doc_id": design_doc.id})
        )
        return {
            **state,
            "node_name": "design",
            "requirement_id": requirement.id,
            "design_doc_id": design_doc.id,
        }

    graph.add_node("design", design_node)
    graph.add_edge(START, "design")
    graph.add_edge("design", END)
    return graph.compile()


def build_delivery_graph():
    dispatcher = RuntimeDispatcher()
    graph = StateGraph(dict)

    def _delivery_llm_logger(state: dict[str, object]) -> LlmRunLogger:
        workspace_root = state.get("workspace_root")
        if isinstance(workspace_root, str) and workspace_root.strip():
            return LlmRunLogger(Path(workspace_root) / "llm_logs")
        return LlmRunLogger(Path(".runtime-data") / "delivery-logs")

    def _run_agent(node_name: str, state: dict[str, object]) -> dict[str, object]:
        runtime_state = RuntimeState(
            project_id=str(state.get("project_id", "delivery-project")),
            run_id=str(state.get("run_id", "delivery-run")),
            task_id=str(state.get("task_id", f"delivery-{node_name}")),
            goal=dict(state),
        )
        agent = dispatcher.get(node_name)
        result = agent.run(runtime_state)
        llm_entry = _consume_agent_llm_log(agent)
        if llm_entry is not None:
            _delivery_llm_logger(state).append(
                run_id=runtime_state.run_id,
                node_name=node_name,
                **llm_entry,
            )
        return {**state, **result.state_patch, "node_name": node_name, "trace": result.trace}

    def dev_node(state: dict[str, object]) -> dict[str, object]:
        return _run_agent("dev", state)

    def qa_node(state: dict[str, object]) -> dict[str, object]:
        return _run_agent("qa", state)

    def quality_node(state: dict[str, object]) -> dict[str, object]:
        return _run_agent("quality", state)

    graph.add_node("dev", dev_node)
    graph.add_node("qa", qa_node)
    graph.add_node("quality", quality_node)
    graph.add_edge(START, "dev")
    graph.add_edge("dev", "qa")
    graph.add_edge("qa", "quality")
    graph.add_edge("quality", END)
    return graph.compile()
