from __future__ import annotations

from pathlib import Path

from studio.schemas.delivery import DeliveryPlan
from studio.schemas.requirement import RequirementCard
from studio.storage.project_binding import preferred_project_id_for_requirement
from studio.storage.workspace import StudioWorkspace


def test_change_request_prefers_completed_mvp_project_id(tmp_path: Path) -> None:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    ws.requirements.save(
        RequirementCard(
            id="req_mvp",
            title="Snake MVP",
            kind="product_mvp",
            status="done",
            project_id="proj_existing",
        )
    )
    change = RequirementCard(
        id="req_change",
        title="Add pause menu",
        kind="change_request",
        project_id="proj_wrong",
    )

    assert preferred_project_id_for_requirement(ws, change) == "proj_existing"


def test_completed_mvp_project_id_can_be_inferred_from_delivery_plan(tmp_path: Path) -> None:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    ws.requirements.save(
        RequirementCard(
            id="req_mvp",
            title="Snake MVP",
            kind="product_mvp",
            status="done",
        )
    )
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_mvp",
            meeting_id="meet_mvp",
            requirement_id="req_mvp",
            project_id="proj_from_plan",
            status="completed",
        )
    )
    change = RequirementCard(
        id="req_change",
        title="Add pause menu",
        kind="change_request",
    )

    assert preferred_project_id_for_requirement(ws, change) == "proj_from_plan"
