from __future__ import annotations

from pathlib import Path

from studio.schemas.delivery import DeliveryPlan, DeliveryTask
from studio.schemas.delivery_events import DeliveryTaskEvent
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.workspace import StudioWorkspace


def test_workspace_persists_delivery_task_events(tmp_path: Path) -> None:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()

    event = DeliveryTaskEvent(
        id="evt_task_001_0001",
        task_id="task_001",
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        agent="dev",
        event_type="task_started",
        message="dev started task Implement game UI.",
        metadata={"attempt_count": 1, "session_id": "sess_dev"},
    )

    ws.delivery_task_events.save(event)
    loaded = ws.delivery_task_events.get("evt_task_001_0001")

    assert loaded.task_id == "task_001"
    assert loaded.event_type == "task_started"
    assert loaded.metadata["session_id"] == "sess_dev"


def test_delivery_service_records_task_event(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    ws = StudioWorkspace(workspace_root)
    ws.ensure_layout()
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="active",
            task_ids=["task_001"],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement game UI",
            description="Build the screen.",
            owner_agent="dev",
            status="ready",
        )
    )

    service = DeliveryPlanService(workspace_root, project_root=tmp_path)
    event = service.record_task_event(
        "task_001",
        "task_started",
        message="dev started task Implement game UI.",
        metadata={"attempt_count": 1},
    )

    loaded = ws.delivery_task_events.get(event.id)
    assert loaded.task_id == "task_001"
    assert loaded.event_type == "task_started"
    assert loaded.metadata["attempt_count"] == 1
