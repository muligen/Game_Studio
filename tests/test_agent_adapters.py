from studio.agents.planner import PlannerAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent
from studio.schemas.runtime import NodeDecision, RuntimeState


def test_planner_agent_sets_first_pending_nodes() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = PlannerAgent().run(state)
    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["pending_nodes"] == ["worker", "reviewer"]


def test_reviewer_agent_requests_retry_for_missing_title() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = ReviewerAgent().run(state, artifact_payload={"summary": "missing title"})
    assert result.decision is NodeDecision.RETRY


def test_worker_agent_produces_design_artifact() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = WorkerAgent().run(state)
    assert result.artifacts[0].artifact_type == "design_brief"
