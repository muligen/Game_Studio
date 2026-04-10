import pytest
from pydantic import ValidationError

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


def test_runtime_state_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc:
        RuntimeState(
            project_id="demo-project",
            run_id="run-001",
            task_id="task-001",
            goal={"prompt": "ok"},
            not_a_real_field=1,
        )
    assert "extra" in str(exc.value).lower()


def test_runtime_state_rejects_empty_project_id() -> None:
    with pytest.raises(ValidationError):
        RuntimeState(
            project_id="   ",
            run_id="run-001",
            task_id="task-001",
            goal={"prompt": "x"},
        )


def test_goal_rejects_non_json_safe_values() -> None:
    with pytest.raises(ValidationError):
        RuntimeState(
            project_id="demo-project",
            run_id="run-001",
            task_id="task-001",
            goal={"bad": object()},
        )


def test_artifact_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ArtifactRecord(
            artifact_id="a",
            artifact_type="t",
            version=0,
            source_node="n",
        )


def test_artifact_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc:
        ArtifactRecord(
            artifact_id="a",
            artifact_type="t",
            source_node="n",
            surprise=True,
        )
    assert "extra" in str(exc.value).lower()


def test_artifact_payload_rejects_non_json_safe_values() -> None:
    with pytest.raises(ValidationError):
        ArtifactRecord(
            artifact_id="a",
            artifact_type="t",
            source_node="n",
            payload={"x": object()},
        )


def test_parent_artifact_id_rejects_blank_string() -> None:
    with pytest.raises(ValidationError):
        ArtifactRecord(
            artifact_id="a",
            artifact_type="t",
            source_node="n",
            parent_artifact_id="   ",
        )


def test_node_result_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc:
        NodeResult(
            decision=NodeDecision.CONTINUE,
            oops="no",
        )
    assert "extra" in str(exc.value).lower()
