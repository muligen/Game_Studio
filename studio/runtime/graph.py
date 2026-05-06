from __future__ import annotations

import json
import logging
import operator
import traceback
import uuid
from concurrent.futures import as_completed
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from studio.artifacts.registry import ArtifactRegistry
from studio.domain.requirement_flow import transition_requirement
from studio.memory.store import MemoryStore
from studio.observability import LangfuseTelemetry
from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.dispatcher import RuntimeDispatcher
from studio.runtime.llm_logs import LlmRunLogger
from studio.runtime import pool as agent_pool
from studio.schemas.design_doc import DesignDoc
from studio.schemas.runtime import PlanState, RuntimeState
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


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
        consume = getattr(agent, "consume_debug_record", None)
        if not callable(consume):
            return None
    entry = consume()
    if not isinstance(entry, dict):
        return None
    return entry


def _append_llm_log_entry(
    logger: LlmRunLogger,
    *,
    run_id: str,
    node_name: str,
    entry: dict[str, object],
    telemetry_metadata: dict[str, object] | None = None,
) -> None:
    metadata: dict[str, object] = {}
    if isinstance(telemetry_metadata, dict):
        metadata.update(telemetry_metadata)
    langfuse_metadata = entry.get("langfuse")
    if isinstance(langfuse_metadata, dict):
        metadata.update({str(key): value for key, value in langfuse_metadata.items()})

    logger.append(
        run_id=run_id,
        node_name=node_name,
        prompt=str(entry.get("prompt", "")),
        context=entry.get("context") if isinstance(entry.get("context"), dict) else {},
        reply=entry.get("reply"),
        metadata=metadata or None,
    )


def _meeting_id_for_requirement(requirement_id: str) -> str:
    return f"meeting_{requirement_id.split('_')[-1]}"


def _meeting_transcript_event(
    *,
    node_name: str,
    agent_role: str,
    agent: object,
) -> dict[str, object] | None:
    entry = _consume_agent_llm_log(agent)
    if entry is None:
        return None
    reply = entry.get("reply")
    message = "Structured transcript event"
    if isinstance(reply, str) and reply.strip():
        message = reply.strip()
    elif isinstance(reply, dict):
        for key in ("summary", "title", "reason", "reply"):
            value = reply.get(key)
            if isinstance(value, str) and value.strip():
                message = value.strip()
                break
    return {
        "agent_role": agent_role,
        "node_name": node_name,
        "kind": "llm",
        "message": message,
        "prompt": entry.get("prompt"),
        "context": entry.get("context"),
        "reply": reply,
    }


def build_demo_runtime(root: Path, force_review_retry: bool = False):
    """Each invoke gets a unique run context so the same compiled graph can be reused safely."""
    dispatcher = RuntimeDispatcher()
    artifact_registry = ArtifactRegistry(root / "artifacts")
    memory_store = MemoryStore(root / "memory")
    checkpoints = CheckpointManager(root / "checkpoints")
    llm_logs = LlmRunLogger(root / "logs")
    telemetry = LangfuseTelemetry.from_project_root(Path.cwd())

    def _checkpoint_key(run_id: str, node_name: str) -> str:
        return f"{run_id}-{node_name}"

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        run_id = _new_run_id()
        with telemetry.node_span(
            name="planner",
            metadata={
                "graph": "game_studio_demo",
                "run_id": run_id,
                "task_id": f"{run_id}-planner",
                "node_name": "planner",
            },
            input={"goal": state},
        ) as span:
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
            span.update(output={"current_node": merged.plan.current_node})
            return merged.model_dump(mode="json")

    def worker_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        run_id = runtime_state.run_id
        with telemetry.node_span(
            name="worker",
            metadata={
                "graph": "game_studio_demo",
                "run_id": run_id,
                "task_id": f"{run_id}-worker",
                "node_name": "worker",
            },
            input={"goal": runtime_state.goal},
        ) as span:
            session_tag = _session_tag_for_run(run_id)
            runtime_state = runtime_state.model_copy(update={"task_id": f"{run_id}-worker"})
            agent = dispatcher.get("worker")
            result = agent.run(runtime_state)
            llm_entry = _consume_agent_llm_log(agent)
            if llm_entry is not None:
                _append_llm_log_entry(
                    llm_logs,
                    run_id=run_id,
                    node_name="worker",
                    entry=llm_entry,
                    telemetry_metadata=telemetry.current_metadata(),
                )
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
            span.update(
                metadata={
                    "fallback_used": bool(result.trace.get("fallback_used", False)),
                    "fallback_reason": str(result.trace.get("fallback_reason", "")),
                },
                output={"current_node": merged.plan.current_node, "artifact_count": len(stored)},
            )
            return merged.model_dump(mode="json")

    def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        run_id = runtime_state.run_id
        with telemetry.node_span(
            name="reviewer",
            metadata={
                "graph": "game_studio_demo",
                "run_id": run_id,
                "task_id": f"{run_id}-reviewer",
                "node_name": "reviewer",
            },
            input={"artifact_count": len(runtime_state.artifacts)},
        ) as span:
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
                span.update(
                    metadata={"status": "needs_attention"},
                    output={"reason": "missing_artifact"},
                )
                return updated.model_dump(mode="json")

            payload = {} if force_review_retry else dict(runtime_state.artifacts[0].payload)
            agent = dispatcher.get("reviewer")
            result = agent.run(runtime_state, artifact_payload=payload)
            llm_entry = _consume_agent_llm_log(agent)
            if llm_entry is not None:
                _append_llm_log_entry(
                    llm_logs,
                    run_id=run_id,
                    node_name="reviewer",
                    entry=llm_entry,
                    telemetry_metadata=telemetry.current_metadata(),
                )
            risks = list(runtime_state.risks)
            patch_risks = result.state_patch.get("risks")
            if isinstance(patch_risks, list):
                risks.extend(str(item) for item in patch_risks)
            if result.decision.value == "retry":
                risks.append("review retry requested")
            status = "needs_attention" if result.decision.value == "retry" else "completed"
            updated = _merge_runtime_state(
                runtime_state,
                state_patch=result.state_patch,
                node_name="reviewer",
                trace=result.trace,
                status=status,
                overrides={"risks": risks},
            )
            checkpoints.save(_checkpoint_key(run_id, "reviewer"), updated)
            span.update(
                metadata={"decision": result.decision.value, "status": status},
                output={"risk_count": len(risks)},
            )
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
    from studio.agents.design import DesignAgent

    graph = StateGraph(dict)
    lf_telemetry = LangfuseTelemetry.from_project_root(Path.cwd())

    def design_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        workspace = StudioWorkspace(Path(workspace_root))
        workspace.ensure_layout()
        requirement = workspace.requirements.get(requirement_id)

        # Check if this is a rework (sent_back design doc exists)
        sent_back_reason: str | None = None
        if requirement.design_doc_id:
            try:
                existing_doc = workspace.design_docs.get(requirement.design_doc_id)
                sent_back_reason = existing_doc.sent_back_reason
            except FileNotFoundError:
                pass

        # Only transition to designing if not already there
        if requirement.status == "draft":
            requirement = transition_requirement(requirement, "designing")
            workspace.requirements.save(requirement)

        # Run DesignAgent
        agent = DesignAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="design-project",
            run_id=_new_run_id(),
            task_id=f"design-{requirement.id}",
            goal={
                "prompt": requirement.title,
                "requirement_id": requirement.id,
                **({"sent_back_reason": sent_back_reason} if sent_back_reason else {}),
            },
        )
        with lf_telemetry.node_span(
            name="design",
            metadata={
                "graph": "studio_design_workflow",
                "requirement_id": requirement_id,
                "node_name": "design",
                "agent_role": "design",
            },
            input={"goal": runtime_state.goal},
        ) as span:
            result = agent.run(runtime_state)
            span.update(
                metadata={"fallback_used": bool(result.trace.get("fallback_used", False))},
                output={"task_id": runtime_state.task_id},
            )

        # Extract agent output from telemetry
        brief = result.state_patch.get("telemetry", {}).get("design_brief", {})
        title = brief.get("title", f"{requirement.title} Design")
        summary = brief.get("summary", requirement.title)
        core_rules = brief.get("core_rules", [])
        acceptance_criteria = brief.get("acceptance_criteria", [])
        open_questions = brief.get("open_questions", [])

        # Create or overwrite design doc
        design_doc_id = requirement.design_doc_id or f"design_{requirement.id.split('_')[-1]}"
        design_doc = DesignDoc(
            id=design_doc_id,
            requirement_id=requirement.id,
            title=str(title),
            summary=str(summary),
            core_rules=[str(r) for r in core_rules],
            acceptance_criteria=[str(c) for c in acceptance_criteria],
            open_questions=[str(q) for q in open_questions],
            status="pending_user_review",
        )

        # Transition requirement to pending_user_review
        pending_review = transition_requirement(requirement, "pending_user_review")
        updated_req = pending_review.model_copy(update={"design_doc_id": design_doc.id})

        workspace.design_docs.save(design_doc)
        workspace.requirements.save(updated_req)

        return {
            **state,
            "node_name": "design",
            "requirement_id": requirement.id,
            "design_doc_id": design_doc.id,
            "fallback_used": result.trace.get("fallback_used", False),
        }

    graph.add_node("design", design_node)
    graph.add_edge(START, "design")
    graph.add_edge("design", END)
    return graph.compile()


class _DeliveryState(TypedDict, total=False):
    workspace_root: str
    project_root: str
    plan_id: str
    runner_status: str
    executed_task_ids: list[str]
    failed_task_ids: list[str]
    context_warnings: list[str]


def build_delivery_graph():
    from studio.storage.delivery_plan_service import DeliveryPlanService
    from studio.storage.git_tracker import GitDiffResult, GitTracker

    dispatcher = RuntimeDispatcher()
    lf_telemetry = LangfuseTelemetry.from_project_root(Path.cwd())

    class _WorkspaceStubAgent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state: RuntimeState, **kwargs: object):
            from studio.schemas.runtime import NodeDecision, NodeResult

            project_dir = Path(str(state.goal["project_dir"]))
            debug_dir = project_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{self.role}-context.json").write_text(
                json.dumps(state.goal, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if self.role == "art":
                art_guide = project_dir / "art" / "ART_GUIDE.md"
                art_guide.parent.mkdir(parents=True, exist_ok=True)
                art_guide.write_text("# Art Guide\n\nUse Pixel art for the Snake MVP.\n", encoding="utf-8")
            elif self.role == "dev":
                index = project_dir / "game" / "index.html"
                index.parent.mkdir(parents=True, exist_ok=True)
                index.write_text("<!doctype html><canvas data-style=\"pixel\"></canvas>\n", encoding="utf-8")
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={
                    "plan": {"current_node": self.role},
                    "telemetry": {
                        f"{self.role}_report": {
                            "summary": f"{self.role} stub completed",
                            "changes": [],
                            "checks": ["stub execution"],
                            "follow_ups": [],
                        }
                    },
                },
                trace={"node": self.role, "llm_provider": "stub", "fallback_used": False},
            )

    def _project_files(project_dir: Path) -> list[str]:
        if not project_dir.exists():
            return []
        return sorted(
            path.relative_to(project_dir).as_posix()
            for path in project_dir.rglob("*")
            if path.is_file()
        )

    def _read_artifact_excerpt(project_dir: Path, rel_path: str) -> dict[str, str]:
        path = project_dir / rel_path
        suffix = path.suffix.lower()
        if suffix not in {".md", ".txt", ".json", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}:
            return {"path": rel_path, "excerpt": ""}
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return {"path": rel_path, "excerpt": ""}
        return {"path": rel_path, "excerpt": text[:3000]}

    def _resolved_decisions(ws: StudioWorkspace, plan: Any) -> list[dict[str, str]]:
        if not plan.decision_gate_id:
            return []
        gate = ws.decision_gates.get(plan.decision_gate_id)
        if gate.status != "resolved":
            return []
        return [
            {
                "id": item.id,
                "question": item.question,
                "resolution": str(item.resolution or ""),
            }
            for item in gate.items
            if item.resolution
        ]

    def _task_context(
        *,
        ws: StudioWorkspace,
        plan: Any,
        task: Any,
        tracker: GitTracker,
    ) -> tuple[dict[str, object], list[str], list[str], list[str]]:
        meeting = ws.meetings.get(task.meeting_id)
        requirement = ws.requirements.get(task.requirement_id)
        project_dir = tracker.project_dir
        decisions = _resolved_decisions(ws, plan)
        dependency_results: list[dict[str, object]] = []
        dependency_artifact_files: list[str] = []
        artifact_excerpts: list[dict[str, str]] = []
        warnings: list[str] = []

        for dep_id in task.depends_on_task_ids:
            dep = ws.delivery_tasks.get(dep_id)
            if not dep.execution_result_id:
                warnings.append(f"dependency {dep.title} has no execution result")
                continue
            try:
                result = ws.execution_results.get(dep.execution_result_id)
            except FileNotFoundError:
                warnings.append(f"dependency {dep.title} result file is missing")
                continue
            payload = {
                "task_id": dep.id,
                "title": dep.title,
                "agent": result.agent,
                "summary": result.summary,
                "changed_files": list(result.changed_files),
                "output_artifact_ids": list(result.output_artifact_ids),
                "tests_or_checks": list(result.tests_or_checks),
                "follow_up_notes": list(result.follow_up_notes),
            }
            dependency_results.append(payload)
            files = list(dict.fromkeys([*result.output_artifact_ids, *result.changed_files]))
            if not files:
                warnings.append(f"dependency {dep.title} produced no files")
            for rel_path in files:
                if rel_path not in dependency_artifact_files:
                    dependency_artifact_files.append(rel_path)
                    artifact_excerpts.append(_read_artifact_excerpt(project_dir, rel_path))

        context = {
            "prompt": "\n\n".join(
                [
                    "Delivery task is approved and ready for autonomous execution.",
                    "Do not ask the user questions and do not call AskQuestion.",
                    "Use available tools directly. If anything is ambiguous, make the smallest reasonable assumption and record it in follow_ups.",
                    f"Task: {task.title}",
                    task.description,
                ]
            ),
            "delivery_execution": True,
            "task_id": task.id,
            "task_title": task.title,
            "task_description": task.description,
            "owner_agent": task.owner_agent,
            "acceptance_criteria": list(task.acceptance_criteria),
            "project_dir": str(tracker.project_dir),
            "requirement": requirement.model_dump(mode="json"),
            "meeting": meeting.model_dump(mode="json"),
            "meeting_decisions": list(meeting.decisions),
            "meeting_consensus": list(meeting.consensus_points),
            "resolved_decisions": decisions,
            "dependency_results": dependency_results,
            "dependency_artifact_files": dependency_artifact_files,
            "dependency_artifact_excerpts": artifact_excerpts,
            "project_files": _project_files(project_dir),
            "context_warnings": warnings,
        }
        return (
            context,
            [str(item["id"]) for item in decisions],
            [str(item["task_id"]) for item in dependency_results],
            warnings,
        )

    def _run_one_task(
        *,
        workspace_root: Path,
        project_root: Path,
        task_id: str,
    ) -> dict[str, object]:
        service = DeliveryPlanService(workspace_root, project_root=project_root)
        ws = service._ws
        task = ws.delivery_tasks.get(task_id)
        started_task = service.start_task(task_id)
        plan = ws.delivery_plans.get(started_task.plan_id)
        tracker = GitTracker(repo_root=project_root, project_id=started_task.project_id)
        tracker.ensure_project_dir()
        pre_state: dict[str, str] = {}
        try:
            pre_state = tracker.capture_state()
        except Exception:
            logger.warning("Failed to capture pre-execution state for %s", started_task.id)

        goal, decision_used, dependency_used, context_warnings = _task_context(
            ws=ws,
            plan=plan,
            task=started_task,
            tracker=tracker,
        )
        runtime_state = RuntimeState(
            project_id=started_task.project_id,
            run_id=f"delivery-{plan.id}",
            task_id=started_task.id,
            goal=goal,
        )

        with lf_telemetry.node_span(
            name=f"delivery:{started_task.owner_agent}",
            metadata={
                "graph": "studio_delivery_workflow",
                "plan_id": plan.id,
                "task_id": started_task.id,
                "node_name": "delivery_task",
                "agent_role": started_task.owner_agent,
            },
            input={"goal": goal},
        ) as span:
            # E2E-only hook: lets Playwright assert context sharing without real LLM calls.
            if (workspace_root / "e2e_stub_delivery_agents").exists():
                agent = _WorkspaceStubAgent(started_task.owner_agent)
            else:
                agent = dispatcher.get(started_task.owner_agent)
            result = agent.run(runtime_state)
            llm_entry = _consume_agent_llm_log(agent)
            if llm_entry is not None:
                _append_llm_log_entry(
                    LlmRunLogger(workspace_root / "logs"),
                    run_id=f"delivery-{plan.id}",
                    node_name=started_task.id,
                    entry=llm_entry,
                    telemetry_metadata=lf_telemetry.current_metadata(),
                )

            diff = GitDiffResult(changed_files=[])
            try:
                diff = tracker.detect_changes(pre_state)
                if diff.has_changes:
                    try:
                        tracker.add_and_commit(
                            f"Task {started_task.id}: {started_task.title}\n\nAgent: {started_task.owner_agent}"
                        )
                    except Exception:
                        logger.debug("Skipping git commit for delivery task %s", started_task.id, exc_info=True)
            except Exception:
                logger.warning("Failed to detect project changes for task %s", started_task.id)

            changed_files = [change.path for change in diff.changed_files]
            summary = f"{started_task.owner_agent} completed: {started_task.title}"
            checks: list[str] = []
            follow_ups: list[str] = []
            telemetry = result.state_patch.get("telemetry", {}) if result else {}
            if isinstance(telemetry, dict):
                report_key = next(
                    (key for key in telemetry if str(key).endswith("_report") or str(key).endswith("_brief")),
                    None,
                )
                report = telemetry.get(report_key, {}) if report_key else {}
                if isinstance(report, dict):
                    summary = str(report.get("summary") or summary)
                    checks = [str(item) for item in report.get("checks", [])]
                    follow_ups = [str(item) for item in report.get("follow_ups", [])]
            if result and result.trace.get("fallback_used"):
                context_warnings.append("agent used fallback output")

            completed = service.complete_task(
                task_id=started_task.id,
                summary=summary,
                output_artifact_ids=changed_files,
                changed_files=changed_files,
                tests_or_checks=checks,
                follow_up_notes=follow_ups,
                dependency_context_used=dependency_used,
                decision_context_used=decision_used,
                context_warnings=context_warnings,
            )
            span.update(
                metadata={"changed_file_count": len(changed_files)},
                output={"task_id": started_task.id, "changed_files": changed_files},
            )
        return {
            "task_id": started_task.id,
            "changed_files": changed_files,
            "execution_result": completed["execution_result"].model_dump(mode="json"),
            "context_warnings": context_warnings,
        }

    def prepare_context_node(state: _DeliveryState) -> dict[str, object]:
        workspace_root = Path(_require_state_str(state, "workspace_root"))
        plan_id = _require_state_str(state, "plan_id")
        project_root_raw = state.get("project_root")
        project_root = Path(str(project_root_raw)) if project_root_raw else workspace_root.parent
        ws = StudioWorkspace(workspace_root)
        ws.ensure_layout()
        plan = ws.delivery_plans.get(plan_id)
        if plan.status == "awaiting_user_decision":
            return {**state, "runner_status": "waiting_for_decision"}
        return {
            **state,
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
            "runner_status": "running",
            "executed_task_ids": [],
            "failed_task_ids": [],
            "context_warnings": [],
        }

    def run_delivery_node(state: _DeliveryState) -> dict[str, object]:
        if state.get("runner_status") == "waiting_for_decision":
            return dict(state)
        workspace_root = Path(_require_state_str(state, "workspace_root"))
        project_root = Path(_require_state_str(state, "project_root"))
        plan_id = _require_state_str(state, "plan_id")
        executed = list(state.get("executed_task_ids", []))
        failed: list[str] = []
        all_warnings = list(state.get("context_warnings", []))

        while True:
            ws = StudioWorkspace(workspace_root)
            plan = ws.delivery_plans.get(plan_id)
            tasks = [ws.delivery_tasks.get(task_id) for task_id in plan.task_ids]
            ready = [task for task in tasks if task.status == "ready"]
            if not ready:
                incomplete = [task for task in tasks if task.status != "done"]
                if incomplete:
                    return {
                        **state,
                        "runner_status": "failed",
                        "executed_task_ids": executed,
                        "failed_task_ids": [task.id for task in incomplete],
                        "context_warnings": [*all_warnings, "delivery graph stalled with incomplete tasks"],
                    }
                return {
                    **state,
                    "runner_status": "completed",
                    "executed_task_ids": executed,
                    "failed_task_ids": failed,
                    "context_warnings": all_warnings,
                }

            futures = {
                agent_pool.submit_agent(
                    task.owner_agent,
                    task.requirement_id,
                    task.title,
                    _run_one_task,
                    workspace_root=workspace_root,
                    project_root=project_root,
                    task_id=task.id,
                ): task.id
                for task in ready
            }
            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    logger.exception("Delivery graph task %s failed", task_id)
                    service = DeliveryPlanService(workspace_root, project_root=project_root)
                    service.fail_task(
                        task_id,
                        error_message=str(exc) or exc.__class__.__name__,
                        exception_type=exc.__class__.__name__,
                        traceback_excerpt="".join(
                            traceback.format_exception(type(exc), exc, exc.__traceback__)
                        )[-4000:],
                    )
                    record_error = getattr(agent_pool, "record_task_error", None)
                    if callable(record_error):
                        failed_task = StudioWorkspace(workspace_root).delivery_tasks.get(task_id)
                        record_error(
                            task_id,
                            failed_task.owner_agent,
                            failed_task.requirement_id,
                            "failed",
                            str(exc) or exc.__class__.__name__,
                            {
                                "exception_type": exc.__class__.__name__,
                                "traceback": "".join(
                                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                                )[-4000:],
                            },
                        )
                    failed.append(task_id)
                else:
                    executed.append(str(result["task_id"]))
                    all_warnings.extend(str(item) for item in result.get("context_warnings", []))
            if failed:
                return {
                    **state,
                    "runner_status": "failed",
                    "executed_task_ids": executed,
                    "failed_task_ids": failed,
                    "context_warnings": all_warnings,
                }

    def finalize_delivery_node(state: _DeliveryState) -> dict[str, object]:
        if state.get("runner_status") != "completed":
            return dict(state)
        return dict(state)

    graph = StateGraph(_DeliveryState)
    graph.add_node("prepare_context", prepare_context_node)
    graph.add_node("run_task", run_delivery_node)
    graph.add_node("finalize_delivery", finalize_delivery_node)
    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "run_task")
    graph.add_edge("run_task", "finalize_delivery")
    graph.add_edge("finalize_delivery", END)
    return graph.compile()


class _MeetingState(TypedDict, total=False):
    workspace_root: str
    project_root: str
    requirement_id: str
    user_intent: str
    project_id: str
    agenda: list[str]
    attendees: list[str]
    opinions: Annotated[dict[str, dict[str, object]], operator.or_]
    consensus_points: list[str]
    conflict_points: list[str]
    supplementary: dict[str, str]
    unresolved_conflicts: list[str]
    conflict_resolution_needed: object
    node_name: str
    minutes: dict[str, object]
    meeting_context: dict[str, object]
    transcript_events: Annotated[list[dict[str, object]], operator.add]
    _kickoff_task_id: str


def build_meeting_graph():
    from studio.agents.art import ArtAgent
    from studio.agents.design import DesignAgent
    from studio.agents.dev import DevAgent
    from studio.agents.moderator import ModeratorAgent
    from studio.agents.qa import QaAgent
    from studio.schemas.meeting import AgentOpinion, MeetingMinutes
    from studio.storage.session_registry import SessionRegistry

    _AGENT_MAP: dict[str, type] = {
        "design": DesignAgent,
        "art": ArtAgent,
        "dev": DevAgent,
        "qa": QaAgent,
    }

    _DEFAULT_ATTENDEES = ["design", "dev", "qa"]
    lf_telemetry = LangfuseTelemetry.from_project_root(Path.cwd())

    def _record_kickoff_progress(
        state: _MeetingState,
        *,
        node_name: str,
        agent_role: str,
        status: str = "completed",
    ) -> None:
        task_id = state.get("_kickoff_task_id")
        workspace_root = state.get("workspace_root")
        if not task_id or not workspace_root:
            return
        from datetime import UTC, datetime

        try:
            workspace = StudioWorkspace(Path(str(workspace_root)))
            task = workspace.kickoff_tasks.get(str(task_id))
        except (FileNotFoundError, ValueError, OSError):
            return

        now = datetime.now(UTC).isoformat()
        completed_nodes = list(task.completed_nodes)
        if status == "completed" and node_name not in completed_nodes:
            completed_nodes.append(node_name)
        event: dict[str, object] = {
            "node_name": node_name,
            "agent_role": agent_role,
            "status": status,
            "created_at": now,
        }
        updated = task.model_copy(update={
            "current_node": node_name,
            "completed_nodes": completed_nodes,
            "active_agents": [agent_role] if status == "running" else [],
            "progress_events": [*task.progress_events, event],
            "updated_at": now,
        })
        workspace.kickoff_tasks.save(updated)

    def _filter_attendees(raw_attendees: object, meeting_context: dict[str, object] | None) -> list[str]:
        validated = meeting_context.get("validated_attendees") if isinstance(meeting_context, dict) else None
        if isinstance(validated, list):
            filtered = []
            for attendee in validated:
                role = str(attendee).strip()
                if role in _AGENT_MAP and role not in filtered:
                    filtered.append(role)
            return list(dict.fromkeys(filtered)) if filtered else list(_DEFAULT_ATTENDEES)
        attendees = raw_attendees if isinstance(raw_attendees, list) else []
        known = []
        for attendee in attendees:
            role = str(attendee).strip()
            if role in _AGENT_MAP and role not in known:
                known.append(role)
        return list(dict.fromkeys(known)) if known else list(_DEFAULT_ATTENDEES)

    def _session_for(state: _MeetingState, agent_role: str) -> tuple[str | None, bool]:
        pid = state.get("project_id")
        if not pid:
            return None, False
        ws_root = state.get("workspace_root")
        if not ws_root:
            raise ValueError("workspace_root is required")
        reg = SessionRegistry(Path(str(ws_root)))
        rec = reg.find(str(pid), agent_role)
        if rec is None:
            raise FileNotFoundError(f"project agent session not found: {pid}/{agent_role}")
        resume_session = rec.last_used_at != rec.created_at
        reg.touch(str(pid), agent_role)
        return rec.session_id, resume_session

    def moderator_prepare_node(state: _MeetingState) -> dict:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        user_intent = state.get("user_intent", "")
        meeting_context = state.get("meeting_context")

        workspace = StudioWorkspace(Path(workspace_root))
        requirement = workspace.requirements.get(requirement_id)
        intent = str(user_intent) if user_intent else requirement.title

        session_id, resume_session = _session_for(state, "moderator")
        moderator = ModeratorAgent(
            project_root=Path(project_root),
            session_id=session_id,
            resume_session=resume_session,
        )
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-prepare-{requirement_id}",
            goal={"prompt": intent, "requirement_id": requirement_id},
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_prepare",
            agent_role="moderator",
            status="running",
        )
        with lf_telemetry.node_span(
            name="moderator_prepare",
            metadata={
                "graph": "studio_meeting_workflow",
                "requirement_id": requirement_id,
                "node_name": "moderator_prepare",
                "agent_role": "moderator",
            },
            input={"user_intent": intent, "meeting_context": meeting_context},
        ) as span:
            result = moderator.prepare(runtime_state, meeting_context=meeting_context)
        prep = result.state_patch.get("telemetry", {}).get("moderator_prepare", {})
        transcript_event = _meeting_transcript_event(
            node_name="moderator_prepare",
            agent_role="moderator",
            agent=moderator,
        )

        raw_attendees = prep.get("attendees", list(_DEFAULT_ATTENDEES))
        filtered = _filter_attendees(raw_attendees, meeting_context)
        span.update(output={"attendees": filtered, "agenda_count": len(prep.get("agenda", []))})
        _record_kickoff_progress(
            state,
            node_name="moderator_prepare",
            agent_role="moderator",
        )

        return {
            "node_name": "moderator_prepare",
            "user_intent": intent,
            "agenda": prep.get("agenda", [intent]),
            "attendees": filtered,
            "meeting_context": meeting_context,
            **({"transcript_events": [transcript_event]} if transcript_event is not None else {}),
        }

    def agent_opinion_node(state: _MeetingState) -> dict:
        project_root = _require_state_str(state, "project_root")
        target_role = str(state.get("_target_role", "design"))
        agenda = state.get("agenda", [])
        user_intent = state.get("user_intent", "")
        meeting_context = state.get("meeting_context")

        agent_cls = _AGENT_MAP.get(target_role)
        if agent_cls is None:
            raise ValueError(f"unsupported meeting agent: {target_role}")
        goal: dict[str, object] = {
            "prompt": str(user_intent),
            "phase": "opinion",
            "agenda": agenda,
            "role": target_role,
        }
        if isinstance(meeting_context, dict):
            goal["meeting_context"] = meeting_context
        session_id, resume_session = _session_for(state, target_role)
        agent = agent_cls(
            project_root=Path(project_root),
            session_id=session_id,
            resume_session=resume_session,
        )
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-{target_role}",
            goal=goal,
        )
        _record_kickoff_progress(
            state,
            node_name="agent_opinion",
            agent_role=target_role,
            status="running",
        )
        with lf_telemetry.node_span(
            name="agent_opinion",
            metadata={
                "graph": "studio_meeting_workflow",
                "node_name": "agent_opinion",
                "agent_role": target_role,
            },
            input={"agenda": agenda, "role": target_role},
        ) as span:
            result = agent.run(runtime_state)
        transcript_event = _meeting_transcript_event(
            node_name="agent_opinion",
            agent_role=target_role,
            agent=agent,
        )

        telemetry = result.state_patch.get("telemetry", {})
        report_key = next(
            (k for k in telemetry if k.endswith("_report") or k.endswith("_brief")),
            None,
        )
        report = telemetry.get(report_key, {}) if report_key else {}
        span.update(
            metadata={"fallback_used": bool(result.trace.get("fallback_used", False))},
            output={"report_key": report_key or "", "role": target_role},
        )

        opinion: dict[str, object] = {
            "agent_role": target_role,
            "summary": str(report.get("summary", f"{target_role} opinion")),
            "proposals": [
                str(p)
                for p in report.get("core_rules", report.get("proposals", report.get("changes", [])))
            ],
            "risks": [
                str(r)
                for r in report.get("open_questions", report.get("risks", []))
            ],
            "open_questions": [
                str(q)
                for q in report.get("acceptance_criteria", report.get("open_questions", []))
            ],
        }
        _record_kickoff_progress(
            state,
            node_name="agent_opinion",
            agent_role=target_role,
        )

        return {
            "opinions": {target_role: opinion},
            **({"transcript_events": [transcript_event]} if transcript_event is not None else {}),
        }

    def moderator_summarize_node(state: _MeetingState) -> dict:
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        opinions = state.get("opinions", {})
        meeting_context = state.get("meeting_context")

        session_id, resume_session = _session_for(state, "moderator")
        moderator = ModeratorAgent(
            project_root=Path(project_root),
            session_id=session_id,
            resume_session=resume_session,
        )
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-summarize-{requirement_id}",
            goal={"prompt": str(state.get("user_intent", "")), "requirement_id": requirement_id},
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_summarize",
            agent_role="moderator",
            status="running",
        )
        with lf_telemetry.node_span(
            name="moderator_summarize",
            metadata={
                "graph": "studio_meeting_workflow",
                "requirement_id": requirement_id,
                "node_name": "moderator_summarize",
                "agent_role": "moderator",
            },
            input={"opinion_count": len(opinions)},
        ) as span:
            result = moderator.summarize(runtime_state, opinions=opinions, meeting_context=meeting_context)
        summary = result.state_patch.get("telemetry", {}).get("moderator_summary", {})
        span.update(
            output={
                "consensus_count": len(summary.get("consensus_points", [])),
                "conflict_count": len(summary.get("conflict_points", [])),
            }
        )
        transcript_event = _meeting_transcript_event(
            node_name="moderator_summarize",
            agent_role="moderator",
            agent=moderator,
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_summarize",
            agent_role="moderator",
        )

        return {
            "node_name": "moderator_summarize",
            "consensus_points": summary.get("consensus_points", []),
            "conflict_points": summary.get("conflict_points", []),
            "conflict_resolution_needed": summary.get("conflict_resolution_needed", False),
            **({"transcript_events": [transcript_event]} if transcript_event is not None else {}),
        }

    def moderator_discussion_node(state: _MeetingState) -> dict:
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        opinions = state.get("opinions", {})
        conflict_points = state.get("conflict_points", [])
        meeting_context = state.get("meeting_context")

        session_id, resume_session = _session_for(state, "moderator")
        moderator = ModeratorAgent(
            project_root=Path(project_root),
            session_id=session_id,
            resume_session=resume_session,
        )
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-discussion-{requirement_id}",
            goal={"prompt": str(state.get("user_intent", "")), "requirement_id": requirement_id},
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_discussion",
            agent_role="moderator",
            status="running",
        )
        with lf_telemetry.node_span(
            name="moderator_discussion",
            metadata={
                "graph": "studio_meeting_workflow",
                "requirement_id": requirement_id,
                "node_name": "moderator_discussion",
                "agent_role": "moderator",
            },
            input={"conflict_count": len(conflict_points)},
        ) as span:
            result = moderator.discuss(
                runtime_state,
                conflicts=conflict_points,
                opinions=opinions,
                meeting_context=meeting_context,
            )
        discussion = result.state_patch.get("telemetry", {}).get("moderator_discussion", {})
        span.update(output={"unresolved_count": len(discussion.get("unresolved_conflicts", []))})
        transcript_event = _meeting_transcript_event(
            node_name="moderator_discussion",
            agent_role="moderator",
            agent=moderator,
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_discussion",
            agent_role="moderator",
        )

        return {
            "node_name": "moderator_discussion",
            "supplementary": discussion.get("supplementary", {}),
            "unresolved_conflicts": discussion.get("unresolved_conflicts", []),
            **({"transcript_events": [transcript_event]} if transcript_event is not None else {}),
        }

    def moderator_minutes_node(state: _MeetingState) -> dict:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        meeting_context = state.get("meeting_context")

        workspace = StudioWorkspace(Path(workspace_root))

        session_id, resume_session = _session_for(state, "moderator")
        moderator = ModeratorAgent(
            project_root=Path(project_root),
            session_id=session_id,
            resume_session=resume_session,
        )
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-minutes-{requirement_id}",
            goal={"prompt": str(state.get("user_intent", "")), "requirement_id": requirement_id},
        )
        _record_kickoff_progress(
            state,
            node_name="moderator_minutes",
            agent_role="moderator",
            status="running",
        )
        all_context: dict[str, object] = {
            "agenda": state.get("agenda", []),
            "opinions": state.get("opinions", {}),
            "consensus_points": state.get("consensus_points", []),
            "conflict_points": state.get("conflict_points", []),
        }
        if isinstance(meeting_context, dict):
            all_context["meeting_context"] = meeting_context
        supplementary_raw = state.get("supplementary")
        if isinstance(supplementary_raw, dict):
            all_context["supplementary"] = {str(k): str(v) for k, v in supplementary_raw.items()}
        unresolved = state.get("unresolved_conflicts")
        if isinstance(unresolved, list):
            all_context["unresolved_conflicts"] = unresolved
        with lf_telemetry.node_span(
            name="moderator_minutes",
            metadata={
                "graph": "studio_meeting_workflow",
                "requirement_id": requirement_id,
                "node_name": "moderator_minutes",
                "agent_role": "moderator",
            },
            input={"context_keys": sorted(all_context)},
        ) as span:
            result = moderator.minutes(runtime_state, all_context=all_context)
        minutes_data = result.state_patch.get("telemetry", {}).get("moderator_minutes", {})
        span.update(output={"decision_count": len(minutes_data.get("decisions", []))})
        transcript_events = [
            event for event in state.get("transcript_events", []) if isinstance(event, dict)
        ]
        final_transcript_event = _meeting_transcript_event(
            node_name="moderator_minutes",
            agent_role="moderator",
            agent=moderator,
        )
        if final_transcript_event is not None:
            transcript_events.append(final_transcript_event)

        supplementary_base: dict[str, str] = (
            {k: str(v) for k, v in supplementary_raw.items()}
            if isinstance(supplementary_raw, dict)
            else {}
        )

        if not isinstance(meeting_context, dict):
            supplementary_base["compatibility_warning"] = (
                "meeting_context was not provided; attendee list was not validated."
            )

        minutes = MeetingMinutes(
            id=_meeting_id_for_requirement(requirement_id),
            requirement_id=requirement_id,
            title=str(minutes_data.get("title", "Meeting Notes")),
            agenda=[str(a) for a in state.get("agenda", [])],
            attendees=[str(a) for a in state.get("attendees", [])],
            opinions=[
                AgentOpinion(
                    agent_role=str(op["agent_role"]),
                    summary=str(op["summary"]),
                    proposals=[str(p) for p in op.get("proposals", [])],
                    risks=[str(r) for r in op.get("risks", [])],
                    open_questions=[str(q) for q in op.get("open_questions", [])],
                )
                for op in state.get("opinions", {}).values()
            ],
            consensus_points=[str(c) for c in state.get("consensus_points", [])],
            conflict_points=[str(c) for c in state.get("conflict_points", [])],
            supplementary={
                **supplementary_base,
                "moderator_summary": str(minutes_data.get("summary", "")),
            },
            decisions=[str(d) for d in minutes_data.get("decisions", [])],
            action_items=[str(a) for a in minutes_data.get("action_items", [])],
            pending_user_decisions=_pending_user_decisions(minutes_data, unresolved),
            status="completed",
        )

        if hasattr(workspace, "meetings"):
            workspace.meetings.save(minutes)
        if transcript_events:
            workspace.save_meeting_transcript(
                meeting_id=_meeting_id_for_requirement(requirement_id),
                requirement_id=requirement_id,
                project_id=str(state.get("project_id", "")) or None,
                events=transcript_events,
            )
        _record_kickoff_progress(
            state,
            node_name="moderator_minutes",
            agent_role="moderator",
        )

        return {
            "node_name": "moderator_minutes",
            "minutes": minutes.model_dump(),
            **({"transcript_events": transcript_events} if transcript_events else {}),
        }

    def route_to_agents(state: _MeetingState) -> list[Send]:
        attendees = _filter_attendees(state.get("attendees", []), state.get("meeting_context"))
        if not attendees:
            return [Send("moderator_summarize", dict(state))]
        return [Send("agent_opinion", {**state, "_target_role": role}) for role in attendees]

    def _pending_user_decisions(minutes_data: dict[str, object], unresolved: object) -> list[str]:
        pending = [str(d) for d in minutes_data.get("pending_user_decisions", [])]
        if isinstance(unresolved, list):
            for item in unresolved:
                decision = str(item)
                if decision not in pending:
                    pending.append(decision)
        return pending

    def needs_discussion(state: _MeetingState) -> str:
        if state.get("conflict_resolution_needed"):
            return "moderator_discussion"
        return "moderator_minutes"

    graph = StateGraph(_MeetingState)
    graph.add_node("moderator_prepare", moderator_prepare_node)
    graph.add_node("agent_opinion", agent_opinion_node)
    graph.add_node("moderator_summarize", moderator_summarize_node)
    graph.add_node("moderator_discussion", moderator_discussion_node)
    graph.add_node("moderator_minutes", moderator_minutes_node)

    graph.add_edge(START, "moderator_prepare")
    graph.add_conditional_edges("moderator_prepare", route_to_agents, ["agent_opinion", "moderator_summarize"])
    graph.add_edge("agent_opinion", "moderator_summarize")
    graph.add_conditional_edges("moderator_summarize", needs_discussion, ["moderator_discussion", "moderator_minutes"])
    graph.add_edge("moderator_discussion", "moderator_minutes")
    graph.add_edge("moderator_minutes", END)

    return graph.compile()
