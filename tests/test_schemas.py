from studio.schemas.artifact import ArtifactRecord
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


def test_runtime_state_defaults() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a simple 2D game concept"},
    )
    assert state.plan.current_node is None
    assert state.artifacts == []
    assert state.risks == []


def test_node_result_requires_known_decision() -> None:
    result = NodeResult(
        decision=NodeDecision.CONTINUE,
        state_patch={"risks": ["none"]},
        artifacts=[],
        trace={"node": "planner"},
    )
    assert result.decision is NodeDecision.CONTINUE


def test_artifact_record_tracks_lineage() -> None:
    artifact = ArtifactRecord(
        artifact_id="artifact-001",
        artifact_type="design_brief",
        version=2,
        source_node="reviewer",
        parent_artifact_id="artifact-000",
        review_status="approved",
        tags=["concept"],
        payload={"title": "Sky Forge"},
    )
    assert artifact.parent_artifact_id == "artifact-000"
    assert artifact.version == 2
