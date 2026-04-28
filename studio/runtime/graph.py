from __future__ import annotations

import operator
import uuid
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
        consume = getattr(agent, "consume_debug_record", None)
        if not callable(consume):
            return None
    entry = consume()
    if not isinstance(entry, dict):
        return None
    return entry


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
                llm_logs.append(
                    run_id=run_id,
                    node_name="worker",
                    metadata=telemetry.current_metadata(),
                    **llm_entry,
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
                llm_logs.append(
                    run_id=run_id,
                    node_name="reviewer",
                    metadata=telemetry.current_metadata(),
                    **llm_entry,
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


def build_delivery_graph():
    from studio.agents.dev import DevAgent
    from studio.agents.qa import QaAgent
    from studio.agents.quality import QualityAgent

    graph = StateGraph(dict)
    lf_telemetry = LangfuseTelemetry.from_project_root(Path.cwd())

    def _delivery_llm_logger(state: dict[str, object]) -> LlmRunLogger:
        workspace_root = state.get("workspace_root")
        if isinstance(workspace_root, str) and workspace_root.strip():
            return LlmRunLogger(Path(workspace_root) / "llm_logs")
        return LlmRunLogger(Path(".runtime-data") / "delivery-logs")

    def _load_requirement(state: dict[str, object]):
        workspace_root = _require_state_str(state, "workspace_root")
        requirement_id = _require_state_str(state, "requirement_id")
        workspace = StudioWorkspace(Path(workspace_root))
        return workspace, workspace.requirements.get(requirement_id)

    def dev_node(state: dict[str, object]) -> dict[str, object]:
        workspace, requirement = _load_requirement(state)
        project_root = _require_state_str(state, "project_root")

        # Transition approved → implementing
        requirement = transition_requirement(requirement, "implementing")
        workspace.requirements.save(requirement)

        # Run DevAgent
        agent = DevAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="delivery-project",
            run_id=_new_run_id(),
            task_id=f"delivery-dev-{requirement.id}",
            goal={"prompt": requirement.title, "requirement_id": requirement.id},
        )
        with lf_telemetry.node_span(
            name="dev",
            metadata={
                "graph": "studio_delivery_workflow",
                "requirement_id": requirement.id,
                "node_name": "dev",
                "agent_role": "dev",
            },
            input={"goal": runtime_state.goal},
        ) as span:
            result = agent.run(runtime_state)
            span.update(
                metadata={"fallback_used": bool(result.trace.get("fallback_used", False))},
                output={"task_id": runtime_state.task_id},
            )

        # Transition implementing → self_test_passed
        updated = transition_requirement(requirement, "self_test_passed")
        workspace.requirements.save(updated)

        return {
            **state,
            "node_name": "dev",
            "dev_result": result.state_patch,
            "fallback_used": result.trace.get("fallback_used", False),
        }

    def qa_node(state: dict[str, object]) -> dict[str, object]:
        workspace, requirement = _load_requirement(state)
        project_root = _require_state_str(state, "project_root")

        # Transition self_test_passed → testing
        requirement = transition_requirement(requirement, "testing")
        workspace.requirements.save(requirement)

        # Run QaAgent
        agent = QaAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="delivery-project",
            run_id=_new_run_id(),
            task_id=f"delivery-qa-{requirement.id}",
            goal={"prompt": requirement.title, "requirement_id": requirement.id},
        )
        with lf_telemetry.node_span(
            name="qa",
            metadata={
                "graph": "studio_delivery_workflow",
                "requirement_id": requirement.id,
                "node_name": "qa",
                "agent_role": "qa",
            },
            input={"goal": runtime_state.goal},
        ) as span:
            result = agent.run(runtime_state)

        # Determine pass/fail from agent telemetry
        telemetry = result.state_patch.get("telemetry", {})
        passed = telemetry.get("passed", True)
        span.update(
            metadata={
                "fallback_used": bool(result.trace.get("fallback_used", False)),
                "passed": bool(passed),
            },
            output={"task_id": runtime_state.task_id, "passed": bool(passed)},
        )

        if passed:
            # testing → pending_user_acceptance
            updated = transition_requirement(requirement, "pending_user_acceptance")
        else:
            # testing → implementing (rework)
            updated = transition_requirement(requirement, "implementing")
        workspace.requirements.save(updated)

        return {
            **state,
            "node_name": "qa",
            "qa_result": result.state_patch,
            "qa_passed": passed,
            "fallback_used": result.trace.get("fallback_used", False),
        }

    def quality_node(state: dict[str, object]) -> dict[str, object]:
        workspace, requirement = _load_requirement(state)
        project_root = _require_state_str(state, "project_root")

        # Transition pending_user_acceptance → quality_check
        requirement = transition_requirement(requirement, "quality_check")
        workspace.requirements.save(requirement)

        # Run QualityAgent
        agent = QualityAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="delivery-project",
            run_id=_new_run_id(),
            task_id=f"delivery-quality-{requirement.id}",
            goal={"prompt": requirement.title, "requirement_id": requirement.id},
        )
        with lf_telemetry.node_span(
            name="quality",
            metadata={
                "graph": "studio_delivery_workflow",
                "requirement_id": requirement.id,
                "node_name": "quality",
                "agent_role": "quality",
            },
            input={"goal": runtime_state.goal},
        ) as span:
            result = agent.run(runtime_state)

        # Determine pass/fail from agent telemetry
        telemetry = result.state_patch.get("telemetry", {})
        ready = telemetry.get("ready", True)
        span.update(
            metadata={
                "fallback_used": bool(result.trace.get("fallback_used", False)),
                "ready": bool(ready),
            },
            output={"task_id": runtime_state.task_id, "ready": bool(ready)},
        )

        if ready:
            # quality_check → done
            updated = transition_requirement(requirement, "done")
        else:
            # quality_check → implementing (rework)
            updated = transition_requirement(requirement, "implementing")
        workspace.requirements.save(updated)

        return {
            **state,
            "node_name": "quality",
            "quality_result": result.state_patch,
            "quality_ready": ready,
            "fallback_used": result.trace.get("fallback_used", False),
        }

    graph.add_node("dev", dev_node)
    graph.add_node("qa", qa_node)
    graph.add_node("quality", quality_node)
    graph.add_edge(START, "dev")
    graph.add_edge("dev", "qa")
    graph.add_edge("qa", "quality")
    graph.add_edge("quality", END)
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
