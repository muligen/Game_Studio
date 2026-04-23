from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studio.api.websocket import broadcast_entity_changed
from studio.storage.delivery_plan_service import DeliveryPlanService

router = APIRouter(tags=["delivery"])


class GeneratePlanRequest(BaseModel):
    """Request body for generating a delivery plan."""

    project_id: str
    planner_output: dict


class ResolveGateRequest(BaseModel):
    """Request body for resolving a decision gate."""

    resolutions: dict[str, str]


class StartTaskRequest(BaseModel):
    """Request body for starting a delivery task."""

    session_id: str


def _get_service(workspace: str) -> DeliveryPlanService:
    """Create a DeliveryPlanService for the given workspace path."""
    return DeliveryPlanService(Path(workspace) / ".studio-data")


@router.post("/meetings/{meeting_id}/delivery-plan")
async def generate_delivery_plan(
    meeting_id: str,
    workspace: str,
    request: GeneratePlanRequest,
) -> dict:
    """Generate a delivery plan from a completed meeting."""
    service = _get_service(workspace)
    try:
        result = service.generate_plan(
            meeting_id=meeting_id,
            planner_output=request.planner_output,
            project_id=request.project_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_plan",
        entity_id=result["plan"].id,
        action="created",
    )
    return {
        "plan": result["plan"],
        "tasks": result["tasks"],
        "decision_gate": result["decision_gate"],
    }


@router.get("/delivery-board")
async def list_delivery_board(
    workspace: str,
    requirement_id: str | None = None,
) -> dict:
    """List all delivery board items (plans, tasks, decision gates)."""
    service = _get_service(workspace)
    return service.list_board(requirement_id=requirement_id)


@router.post("/kickoff-decision-gates/{gate_id}/resolve")
async def resolve_decision_gate(
    gate_id: str,
    workspace: str,
    request: ResolveGateRequest,
) -> dict:
    """Resolve a kickoff decision gate."""
    service = _get_service(workspace)
    try:
        result = service.resolve_gate(
            gate_id=gate_id,
            resolutions=request.resolutions,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Decision gate not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="decision_gate",
        entity_id=result["gate"].id,
        action="updated",
    )
    return {"gate": result["gate"], "plan": result["plan"]}


@router.post("/delivery-tasks/{task_id}/start")
async def start_delivery_task(
    task_id: str,
    workspace: str,
    request: StartTaskRequest,
) -> dict:
    """Start a delivery task."""
    service = _get_service(workspace)
    try:
        task = service.start_task(
            task_id=task_id,
            session_id=request.session_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_task",
        entity_id=task.id,
        action="updated",
    )
    return task.model_dump()
