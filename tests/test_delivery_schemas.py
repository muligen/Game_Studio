from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.delivery import (
    AgentSessionLease,
    DeliveryPlan,
    DeliveryPlanStatus,
    DeliveryTask,
    DeliveryTaskStatus,
    GateItem,
    GateStatus,
    KickoffDecisionGate,
    MeetingSnapshot,
    TaskExecutionResult,
)


# ---------------------------------------------------------------------------
# MeetingSnapshot
# ---------------------------------------------------------------------------


def test_meeting_snapshot_basic():
    snap = MeetingSnapshot(
        meeting_title="Sprint Review",
        relevant_decisions=["Use Unity"],
        relevant_consensus=["Agree on MVP scope"],
        task_acceptance_notes=["Must pass CI"],
    )
    assert snap.meeting_title == "Sprint Review"
    assert snap.relevant_decisions == ["Use Unity"]
    assert snap.relevant_consensus == ["Agree on MVP scope"]
    assert snap.task_acceptance_notes == ["Must pass CI"]


def test_meeting_snapshot_defaults():
    snap = MeetingSnapshot(meeting_title="Quick Sync")
    assert snap.relevant_decisions == []
    assert snap.relevant_consensus == []
    assert snap.task_acceptance_notes == []


def test_meeting_snapshot_rejects_empty_title():
    with pytest.raises(ValidationError):
        MeetingSnapshot(meeting_title="   ")


def test_meeting_snapshot_rejects_extra_fields():
    with pytest.raises(ValidationError):
        MeetingSnapshot(meeting_title="Review", unknown="oops")


# ---------------------------------------------------------------------------
# GateItem
# ---------------------------------------------------------------------------


def test_gate_item_basic():
    item = GateItem(
        id="gate_1",
        question="Which engine?",
        context="Need to decide on game engine",
        options=["Unity", "Unreal", "Godot"],
    )
    assert item.id == "gate_1"
    assert item.question == "Which engine?"
    assert item.context == "Need to decide on game engine"
    assert item.options == ["Unity", "Unreal", "Godot"]
    assert item.resolution is None


def test_gate_item_with_resolution():
    item = GateItem(
        id="gate_1",
        question="Which engine?",
        context="Need to decide",
        options=["Unity", "Unreal"],
        resolution="Unity",
    )
    assert item.resolution == "Unity"


def test_gate_item_rejects_empty_id():
    with pytest.raises(ValidationError):
        GateItem(id="", question="Q?", context="C", options=["A"])


def test_gate_item_rejects_empty_question():
    with pytest.raises(ValidationError):
        GateItem(id="g1", question="  ", context="C", options=["A"])


def test_gate_item_rejects_extra_fields():
    with pytest.raises(ValidationError):
        GateItem(
            id="g1", question="Q?", context="C", options=["A"], extra=True
        )


# ---------------------------------------------------------------------------
# DeliveryPlan
# ---------------------------------------------------------------------------


def test_delivery_plan_basic():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert plan.id == "plan_1"
    assert plan.meeting_id == "mtg_1"
    assert plan.requirement_id == "req_1"
    assert plan.project_id == "proj_1"


def test_delivery_plan_default_status():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert plan.status == "awaiting_user_decision"
    assert plan.task_ids == []
    assert plan.decision_gate_id is None
    assert plan.decision_resolution_version is None


def test_delivery_plan_active_with_resolution():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="active",
        task_ids=["task_a", "task_b"],
        decision_gate_id="gate_1",
        decision_resolution_version=2,
    )
    assert plan.status == "active"
    assert plan.task_ids == ["task_a", "task_b"]
    assert plan.decision_gate_id == "gate_1"
    assert plan.decision_resolution_version == 2


def test_delivery_plan_timestamps_auto_set():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert plan.created_at is not None
    assert plan.updated_at is not None


def test_delivery_plan_completed_status():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="completed",
    )
    assert plan.status == "completed"


def test_delivery_plan_cancelled_status():
    plan = DeliveryPlan(
        id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="cancelled",
    )
    assert plan.status == "cancelled"


def test_delivery_plan_rejects_empty_id():
    with pytest.raises(ValidationError):
        DeliveryPlan(
            id="",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
        )


def test_delivery_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DeliveryPlan(
            id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            unknown_field="oops",
        )


# ---------------------------------------------------------------------------
# DeliveryTask
# ---------------------------------------------------------------------------


def test_delivery_task_basic():
    task = DeliveryTask(
        id="task_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Implement login",
        description="Create login flow",
        owner_agent="dev",
    )
    assert task.id == "task_1"
    assert task.plan_id == "plan_1"
    assert task.title == "Implement login"
    assert task.owner_agent == "dev"


def test_delivery_task_default_status():
    task = DeliveryTask(
        id="task_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Implement login",
        description="Create login flow",
        owner_agent="dev",
    )
    assert task.status == "ready"
    assert task.depends_on_task_ids == []
    assert task.execution_result_id is None
    assert task.output_artifact_ids == []
    assert task.acceptance_criteria == []
    assert task.meeting_snapshot is None
    assert task.decision_resolution_version is None


def test_delivery_task_blocked():
    task = DeliveryTask(
        id="task_2",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Write tests",
        description="E2E tests",
        owner_agent="qa",
        status="blocked",
        depends_on_task_ids=["task_1"],
    )
    assert task.status == "blocked"
    assert task.depends_on_task_ids == ["task_1"]


def test_delivery_task_preview():
    task = DeliveryTask(
        id="task_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Draft design",
        description="Design doc",
        owner_agent="design",
        status="preview",
    )
    assert task.status == "preview"


def test_delivery_task_with_meeting_snapshot():
    snap = MeetingSnapshot(
        meeting_title="Sprint Review",
        relevant_decisions=["Use Unity"],
    )
    task = DeliveryTask(
        id="task_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Implement feature",
        description="Feature X",
        owner_agent="dev",
        meeting_snapshot=snap,
    )
    assert task.meeting_snapshot is not None
    assert task.meeting_snapshot.meeting_title == "Sprint Review"


def test_delivery_task_all_statuses():
    valid_statuses: list[DeliveryTaskStatus] = [
        "preview", "blocked", "ready", "in_progress", "review", "done",
        "cancelled",
    ]
    for s in valid_statuses:
        task = DeliveryTask(
            id="task_1",
            plan_id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            title="T",
            description="D",
            owner_agent="dev",
            status=s,
        )
        assert task.status == s


def test_delivery_task_timestamps_auto_set():
    task = DeliveryTask(
        id="task_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="T",
        description="D",
        owner_agent="dev",
    )
    assert task.created_at is not None
    assert task.updated_at is not None


def test_delivery_task_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DeliveryTask(
            id="task_1",
            plan_id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            title="T",
            description="D",
            owner_agent="dev",
            unknown=True,
        )


# ---------------------------------------------------------------------------
# KickoffDecisionGate
# ---------------------------------------------------------------------------


def test_kickoff_decision_gate_basic():
    gate = KickoffDecisionGate(
        id="gate_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert gate.id == "gate_1"
    assert gate.plan_id == "plan_1"


def test_kickoff_decision_gate_default_status():
    gate = KickoffDecisionGate(
        id="gate_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert gate.status == "open"
    assert gate.resolution_version == 0
    assert gate.items == []


def test_kickoff_decision_gate_resolved():
    items = [
        GateItem(
            id="gi_1",
            question="Engine?",
            context="Pick engine",
            options=["Unity", "Unreal"],
            resolution="Unity",
        ),
    ]
    gate = KickoffDecisionGate(
        id="gate_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="resolved",
        resolution_version=1,
        items=items,
    )
    assert gate.status == "resolved"
    assert gate.resolution_version == 1
    assert len(gate.items) == 1
    assert gate.items[0].resolution == "Unity"


def test_kickoff_decision_gate_cancelled():
    gate = KickoffDecisionGate(
        id="gate_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="cancelled",
    )
    assert gate.status == "cancelled"


def test_kickoff_decision_gate_timestamps_auto_set():
    gate = KickoffDecisionGate(
        id="gate_1",
        plan_id="plan_1",
        meeting_id="mtg_1",
        requirement_id="req_1",
        project_id="proj_1",
    )
    assert gate.created_at is not None
    assert gate.updated_at is not None


def test_kickoff_decision_gate_rejects_extra_fields():
    with pytest.raises(ValidationError):
        KickoffDecisionGate(
            id="gate_1",
            plan_id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            unknown="oops",
        )


# ---------------------------------------------------------------------------
# TaskExecutionResult
# ---------------------------------------------------------------------------


def test_task_execution_result_basic():
    result = TaskExecutionResult(
        id="result_1",
        task_id="task_1",
        plan_id="plan_1",
        project_id="proj_1",
        agent="dev",
        session_id="sess_1",
        summary="Implemented feature X",
    )
    assert result.id == "result_1"
    assert result.task_id == "task_1"
    assert result.agent == "dev"
    assert result.summary == "Implemented feature X"
    assert result.output_artifact_ids == []
    assert result.changed_files == []
    assert result.tests_or_checks == []
    assert result.follow_up_notes == []


def test_task_execution_result_with_all_fields():
    result = TaskExecutionResult(
        id="result_1",
        task_id="task_1",
        plan_id="plan_1",
        project_id="proj_1",
        agent="dev",
        session_id="sess_1",
        summary="Completed",
        output_artifact_ids=["art_1", "art_2"],
        changed_files=["src/main.py", "tests/test_main.py"],
        tests_or_checks=["pytest passed", "lint ok"],
        follow_up_notes=["Need perf testing"],
    )
    assert result.output_artifact_ids == ["art_1", "art_2"]
    assert result.changed_files == ["src/main.py", "tests/test_main.py"]
    assert result.tests_or_checks == ["pytest passed", "lint ok"]
    assert result.follow_up_notes == ["Need perf testing"]


def test_task_execution_result_timestamp_auto_set():
    result = TaskExecutionResult(
        id="result_1",
        task_id="task_1",
        plan_id="plan_1",
        project_id="proj_1",
        agent="dev",
        session_id="sess_1",
        summary="Done",
    )
    assert result.created_at is not None


def test_task_execution_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TaskExecutionResult(
            id="result_1",
            task_id="task_1",
            plan_id="plan_1",
            project_id="proj_1",
            agent="dev",
            session_id="sess_1",
            summary="Done",
            extra=True,
        )


# ---------------------------------------------------------------------------
# AgentSessionLease
# ---------------------------------------------------------------------------


def test_agent_session_lease_auto_id():
    lease = AgentSessionLease(
        project_id="proj_1",
        agent="dev",
        task_id="task_1",
        session_id="sess_1",
    )
    assert lease.id == "proj_1_dev"


def test_agent_session_lease_custom_id():
    lease = AgentSessionLease(
        id="custom_id",
        project_id="proj_1",
        agent="dev",
        task_id="task_1",
        session_id="sess_1",
    )
    assert lease.id == "custom_id"


def test_agent_session_lease_default_status():
    lease = AgentSessionLease(
        project_id="proj_1",
        agent="dev",
        task_id="task_1",
        session_id="sess_1",
    )
    assert lease.status == "held"


def test_agent_session_lease_released():
    lease = AgentSessionLease(
        project_id="proj_1",
        agent="dev",
        task_id="task_1",
        session_id="sess_1",
        status="released",
    )
    assert lease.status == "released"


def test_agent_session_lease_timestamps_auto_set():
    lease = AgentSessionLease(
        project_id="proj_1",
        agent="dev",
        task_id="task_1",
        session_id="sess_1",
    )
    assert lease.expires_at is not None
    assert lease.created_at is not None


def test_agent_session_lease_rejects_empty_project_id():
    with pytest.raises(ValidationError):
        AgentSessionLease(
            project_id="",
            agent="dev",
            task_id="task_1",
            session_id="sess_1",
        )


def test_agent_session_lease_rejects_empty_agent():
    with pytest.raises(ValidationError):
        AgentSessionLease(
            project_id="proj_1",
            agent="  ",
            task_id="task_1",
            session_id="sess_1",
        )


def test_agent_session_lease_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AgentSessionLease(
            project_id="proj_1",
            agent="dev",
            task_id="task_1",
            session_id="sess_1",
            unknown="oops",
        )


# ---------------------------------------------------------------------------
# Literal type coverage: DeliveryPlanStatus
# ---------------------------------------------------------------------------


def test_delivery_plan_all_statuses():
    valid: list[DeliveryPlanStatus] = [
        "awaiting_user_decision", "active", "completed", "cancelled",
    ]
    for s in valid:
        plan = DeliveryPlan(
            id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            status=s,
        )
        assert plan.status == s


# ---------------------------------------------------------------------------
# Literal type coverage: GateStatus
# ---------------------------------------------------------------------------


def test_gate_all_statuses():
    valid: list[GateStatus] = ["open", "resolved", "cancelled"]
    for s in valid:
        gate = KickoffDecisionGate(
            id="gate_1",
            plan_id="plan_1",
            meeting_id="mtg_1",
            requirement_id="req_1",
            project_id="proj_1",
            status=s,
        )
        assert gate.status == s
