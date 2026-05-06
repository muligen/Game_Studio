from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from claude_agent_sdk import get_session_messages as sdk_get_session_messages

from studio.agents.profile_loader import AgentProfileLoader
from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.api.websocket import broadcast_entity_changed
from studio.llm import ClaudeRoleError
from studio.runtime.delivery_runner import run_delivery_plan, submit_delivery_plan
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


@router.post("/meetings/{meeting_id}/delivery-plan")
async def generate_delivery_plan(
    meeting_id: str,
    workspace: str,
    request: GeneratePlanRequest,
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
        submit_delivery_plan(
            resolve_workspace_root(workspace),
            resolve_project_root(workspace),
            result["plan"].id,
            runner=run_delivery_plan,
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
        submit_delivery_plan(
            resolve_workspace_root(workspace),
            resolve_project_root(workspace),
            result["plan"].id,
            runner=run_delivery_plan,
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


@router.post("/delivery-tasks/{task_id}/retry")
async def retry_delivery_task(
    task_id: str,
    workspace: str,
) -> dict:
    """Reset a failed delivery task so the delivery runner can execute it again."""
    service = _get_service(workspace)
    try:
        task = service.retry_task(task_id=task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    service.record_task_event(
        task_id, "task_retried",
        message=f"Task {task_id} was reset for retry.",
        metadata={"status": task.status},
    )

    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="delivery_task",
        entity_id=task.id,
        action="updated",
    )
    submit_delivery_plan(
        resolve_workspace_root(workspace),
        resolve_project_root(workspace),
        task.plan_id,
        runner=run_delivery_plan,
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


@router.get("/delivery-tasks/{task_id}/events")
async def get_delivery_task_events(
    task_id: str,
    workspace: str,
) -> dict:
    """Return chronological task events for a delivery task."""
    service = _get_service(workspace)
    try:
        service._ws.delivery_tasks.get(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    events = [
        event for event in service._ws.delivery_task_events.list_all()
        if event.task_id == task_id
    ]
    events.sort(key=lambda event: event.created_at)
    return {"events": [event.model_dump() for event in events]}


@router.get("/delivery-tasks/{task_id}/session")
async def get_delivery_task_session(
    task_id: str,
    workspace: str,
) -> dict:
    """Return Claude session messages attached to a delivery task."""
    service = _get_service(workspace)
    try:
        task = service._ws.delivery_tasks.get(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        session = service._ws.sessions.get(f"{task.project_id}_{task.owner_agent}")
    except FileNotFoundError:
        return {
            "task_id": task.id,
            "project_id": task.project_id,
            "agent": task.owner_agent,
            "session_id": None,
            "messages": [],
        }

    profile = AgentProfileLoader().load(task.owner_agent)
    project_root = resolve_project_root(workspace)
    claude_root = profile.claude_project_root
    if not claude_root.is_absolute():
        claude_root = (project_root / claude_root).resolve()

    try:
        sdk_messages = sdk_get_session_messages(
            session.session_id,
            directory=str(claude_root),
        )
    except Exception:
        sdk_messages = []

    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "agent": task.owner_agent,
        "session_id": session.session_id,
        "messages": [_delivery_session_message(msg) for msg in sdk_messages],
    }


def _delivery_session_message(msg: object) -> dict[str, object]:
    message = getattr(msg, "message", {})
    return {
        "role": str(getattr(msg, "type", "")),
        "content": _extract_content_text(message),
        "uuid": str(getattr(msg, "uuid", "")),
        "blocks": message.get("content", []) if isinstance(message, dict) and isinstance(message.get("content"), list) else [],
    }


def _extract_content_text(message: object) -> str:
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""
