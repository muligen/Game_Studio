from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.api.websocket import broadcast_entity_changed
from studio.llm import ClaudeRoleError
from studio.runtime.graph import build_delivery_graph
from studio.storage.delivery_plan_service import DeliveryPlanService

logger = logging.getLogger(__name__)

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
    dependency_context_used: list[str] = []
    decision_context_used: list[str] = []
    context_warnings: list[str] = []


def _get_service(workspace: str) -> DeliveryPlanService:
    """Create a DeliveryPlanService for the given workspace path."""
    return DeliveryPlanService(
        resolve_workspace_root(workspace),
        project_root=resolve_project_root(workspace),
    )


def run_delivery_plan(workspace_root: Path, project_root: Path, plan_id: str) -> None:
    """Run an active delivery plan through the LangGraph delivery runner."""
    try:
        build_delivery_graph().invoke(
            {
                "workspace_root": str(workspace_root),
                "project_root": str(project_root),
                "plan_id": plan_id,
            }
        )
    except Exception:
        logger.exception("Delivery runner failed for plan %s", plan_id)


@router.post("/meetings/{meeting_id}/delivery-plan")
async def generate_delivery_plan(
    meeting_id: str,
    workspace: str,
    request: GeneratePlanRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate a delivery plan from a completed meeting."""
    try:
        service = _get_service(workspace)
    except Exception as exc:
        logger.exception("Failed to create DeliveryPlanService for workspace=%s", workspace)
        raise HTTPException(status_code=500, detail=f"Service initialization failed: {exc}")
    try:
        result = await run_in_threadpool(
            service.generate_plan,
            meeting_id=meeting_id,
            project_id=request.project_id,
        )
    except FileNotFoundError:
        logger.error("Meeting not found: meeting_id=%s workspace=%s", meeting_id, workspace)
        raise HTTPException(status_code=404, detail="Meeting not found")
    except ValueError as e:
        logger.error("Delivery plan validation error for meeting=%s: %s", meeting_id, e)
        raise HTTPException(status_code=400, detail=str(e))
    except ClaudeRoleError as e:
        logger.error("Claude LLM error during delivery plan generation: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as exc:
        logger.exception("Unexpected error generating delivery plan for meeting=%s", meeting_id)
        raise HTTPException(status_code=500, detail=f"Delivery plan generation failed: {exc}")

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_plan",
        entity_id=result["plan"].id,
        action="created",
    )
    if result["plan"].status == "active":
        background_tasks.add_task(
            run_delivery_plan,
            resolve_workspace_root(workspace),
            resolve_project_root(workspace),
            result["plan"].id,
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
        "runner_status": result.get("runner_status", "idle"),
    }


@router.post("/kickoff-decision-gates/{gate_id}/resolve")
async def resolve_decision_gate(
    gate_id: str,
    workspace: str,
    request: ResolveGateRequest,
    background_tasks: BackgroundTasks,
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
    if result["plan"].status == "active":
        background_tasks.add_task(
            run_delivery_plan,
            resolve_workspace_root(workspace),
            resolve_project_root(workspace),
            result["plan"].id,
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
            dependency_context_used=request.dependency_context_used,
            decision_context_used=request.decision_context_used,
            context_warnings=request.context_warnings,
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
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=result["task"].requirement_id,
        action="updated",
    )
    return {
        "task": result["task"].model_dump(),
        "execution_result": result["execution_result"].model_dump(),
    }
