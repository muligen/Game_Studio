from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from studio.api.websocket import broadcast_entity_changed
from studio.llm import ClaudeRoleError
from studio.storage.delivery_plan_service import DeliveryPlanService

router = APIRouter(tags=["delivery"])


class GeneratePlanRequest(BaseModel):
    """Request body for generating a delivery plan."""

    model_config = ConfigDict(extra="forbid")

    project_id: str


class ResolveGateRequest(BaseModel):
    """Request body for resolving a decision gate."""

    model_config = ConfigDict(extra="forbid")

    resolutions: dict[str, str]


class StartTaskRequest(BaseModel):
    """Request body for starting a delivery task."""

    model_config = ConfigDict(extra="forbid")


class CompleteTaskRequest(BaseModel):
    """Request body for completing a delivery task."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    output_artifact_ids: list[str] = []
    changed_files: list[str] = []
    tests_or_checks: list[str] = []
    follow_up_notes: list[str] = []


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
            project_id=request.project_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ClaudeRoleError as e:
        raise HTTPException(status_code=502, detail=str(e))

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_plan",
        entity_id=result["plan"].id,
        action="created",
    )
    return {
        "plan": result["plan"].model_dump(),
        "tasks": [t.model_dump() for t in result["tasks"]],
        "decision_gate": result["decision_gate"].model_dump() if result["decision_gate"] else None,
    }


@router.get("/delivery-board")
async def list_delivery_board(
    workspace: str,
    requirement_id: str | None = None,
) -> dict:
    """List all delivery board items (plans, tasks, decision gates)."""
    service = _get_service(workspace)
    result = service.list_board(requirement_id=requirement_id)
    return {
        "plans": [p.model_dump() for p in result["plans"]],
        "tasks": [t.model_dump() for t in result["tasks"]],
        "decision_gates": [g.model_dump() for g in result["decision_gates"]],
    }


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
    return {"gate": result["gate"].model_dump(), "plan": result["plan"].model_dump()}


@router.post("/delivery-tasks/{task_id}/start")
async def start_delivery_task(
    task_id: str,
    workspace: str,
    request: StartTaskRequest,
) -> dict:
    """Start a delivery task."""
    service = _get_service(workspace)
    try:
        _ = request
        task = service.start_task(task_id=task_id)
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


@router.post("/delivery-tasks/{task_id}/complete")
async def complete_delivery_task(
    task_id: str,
    workspace: str,
    request: CompleteTaskRequest,
) -> dict:
    """Complete a delivery task, persisting execution results and releasing the lease."""
    service = _get_service(workspace)
    try:
        result = service.complete_task(
            task_id=task_id,
            summary=request.summary,
            output_artifact_ids=request.output_artifact_ids,
            changed_files=request.changed_files,
            tests_or_checks=request.tests_or_checks,
            follow_up_notes=request.follow_up_notes,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_task",
        entity_id=task_id,
        action="updated",
    )
    return {
        "task": result["task"].model_dump(),
        "execution_result": result["execution_result"].model_dump(),
    }
