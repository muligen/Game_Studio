from __future__ import annotations

from studio.schemas.delivery import DeliveryPlan, DeliveryTask, GateItem, KickoffDecisionGate
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.storage.acceptance_contract import build_acceptance_contract
from studio.storage.workspace import StudioWorkspace


def test_contract_merges_sources_and_adds_startup_criteria(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    ws.requirements.save(
        RequirementCard(
            id="req_001",
            title="Snake MVP",
            status="implementing",
            acceptance_criteria=["Arrow keys move the snake"],
        )
    )
    ws.meetings.save(
        MeetingMinutes(
            id="meet_001",
            requirement_id="req_001",
            title="Kickoff",
            status="completed",
            decisions=["Use retro pixel style"],
            consensus_points=["Browser game delivery"],
        )
    )
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="active",
            task_ids=["task_001"],
            decision_gate_id="gate_001",
        )
    )
    ws.decision_gates.save(
        KickoffDecisionGate(
            id="gate_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="resolved",
            items=[
                GateItem(
                    id="style",
                    question="Choose style",
                    context="Visual direction",
                    options=["retro pixel", "minimal"],
                    resolution="retro pixel",
                )
            ],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement controls",
            description="Move with arrows",
            owner_agent="dev",
            status="done",
            acceptance_criteria=["Controls respond under 100ms"],
        )
    )

    contract = build_acceptance_contract(ws, "plan_001")
    texts = [criterion.text for criterion in contract.criteria]

    assert "Arrow keys move the snake" in texts
    assert "Kickoff decision resolved: Choose style -> retro pixel" in texts
    assert "Controls respond under 100ms" in texts
    assert "The project exposes a detectable command to start or preview the game." in texts
    assert "The browser page opens without fatal page errors." in texts
    assert len(texts) == len(set(texts))


def test_contract_does_not_turn_bug_fix_tasks_into_new_acceptance_criteria(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    ws.requirements.save(RequirementCard(id="req_001", title="Snake MVP", status="implementing"))
    ws.meetings.save(
        MeetingMinutes(
            id="meet_001",
            requirement_id="req_001",
            title="Kickoff",
            status="completed",
        )
    )
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="repairing",
            task_ids=["task_001", "bugfix_001"],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement controls",
            description="Move with arrows",
            owner_agent="dev",
            acceptance_criteria=["Controls respond under 100ms"],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="bugfix_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Fix: Produce real evidence for controls",
            description="Produce real evidence for controls",
            owner_agent="qa",
            kind="bug_fix",
            acceptance_criteria=["Produce real evidence for: Controls respond under 100ms"],
        )
    )

    contract = build_acceptance_contract(ws, "plan_001")
    texts = [criterion.text for criterion in contract.criteria]

    assert "Controls respond under 100ms" in texts
    assert "Produce real evidence for: Controls respond under 100ms" not in texts
