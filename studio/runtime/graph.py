from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from studio.artifacts.registry import ArtifactRegistry
from studio.memory.store import MemoryStore
from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.dispatcher import RuntimeDispatcher
from studio.schemas.runtime import PlanState, RuntimeState


def build_demo_runtime(root: Path, force_review_retry: bool = False):
    dispatcher = RuntimeDispatcher()
    artifact_registry = ArtifactRegistry(root / "artifacts")
    memory_store = MemoryStore(root / "memory")
    checkpoints = CheckpointManager(root / "checkpoints")

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState(
            project_id="demo-project",
            run_id="run-001",
            task_id="task-001",
            goal=state,
        )
        result = dispatcher.get("planner").run(runtime_state)
        checkpoints.save("planner", runtime_state)
        patch = dict(result.state_patch)
        plan_in = patch.pop("plan", None)
        if isinstance(plan_in, dict):
            merged_plan = PlanState.model_validate(
                {**runtime_state.plan.model_dump(mode="json"), **plan_in}
            )
            merged = runtime_state.model_copy(update={**patch, "plan": merged_plan})
        else:
            merged = runtime_state.model_copy(update=result.state_patch)
        return merged.model_dump(mode="json")

    def worker_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        result = dispatcher.get("worker").run(runtime_state)
        stored = [artifact_registry.save(artifact) for artifact in result.artifacts]
        memory_store.put("run", "run-001-summary", {"summary": "worker produced concept draft"})
        plan_patch = result.state_patch.get("plan")
        if not isinstance(plan_patch, dict):
            plan_patch = {}
        merged_plan = PlanState.model_validate(
            {**runtime_state.plan.model_dump(mode="json"), **plan_patch}
        )
        updated = runtime_state.model_copy(
            update={
                "artifacts": stored,
                "plan": merged_plan,
            }
        )
        checkpoints.save("worker", updated)
        return updated.model_dump(mode="json")

    def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        payload = {} if force_review_retry else dict(runtime_state.artifacts[0].payload)
        result = dispatcher.get("reviewer").run(runtime_state, artifact_payload=payload)
        risks = ["review retry requested"] if result.decision.value == "retry" else []
        status = "needs_attention" if risks else "completed"
        plan_patch = result.state_patch.get("plan")
        if not isinstance(plan_patch, dict):
            plan_patch = {}
        merged_plan = PlanState.model_validate(
            {**runtime_state.plan.model_dump(mode="json"), **plan_patch}
        )
        updated = runtime_state.model_copy(
            update={
                "risks": risks,
                "telemetry": {"status": status},
                "plan": merged_plan,
            }
        )
        checkpoints.save("reviewer", updated)
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
