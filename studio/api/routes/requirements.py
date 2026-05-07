from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studio.api.workspace_paths import resolve_workspace_root
from studio.api.websocket import broadcast_entity_changed
from studio.schemas.artifact import StrippedNonEmptyStr
from studio.schemas.requirement import (
    RequirementCard,
    RequirementKind,
    RequirementPriority,
    RequirementStatus,
)
from studio.storage.project_binding import completed_mvp_project_id
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/requirements", tags=["requirements"])


class CreateRequirementRequest(BaseModel):
    """Request model for creating a requirement."""

    title: StrippedNonEmptyStr
    priority: RequirementPriority = "medium"


class TransitionRequirementRequest(BaseModel):
    """Request model for transitioning a requirement status."""

    next_status: RequirementStatus


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance, ensuring it exists."""
    workspace_path = resolve_workspace_root(workspace)
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_requirements(workspace: str) -> list[RequirementCard]:
    """List all requirements in the workspace."""
    store = _get_workspace(workspace)
    return store.requirements.list_all()


@router.post("")
async def create_requirement(
    workspace: str,
    request: CreateRequirementRequest,
) -> RequirementCard:
    """Create a new requirement."""
    from uuid import uuid4

    store = _get_workspace(workspace)
    store.ensure_layout()

    existing = store.requirements.list_all()
    mvp_done = any(
        r.kind == "product_mvp" and r.status == "done"
        for r in existing
    )
    kind: RequirementKind = "change_request" if mvp_done else "product_mvp"
    project_id = completed_mvp_project_id(store) if kind == "change_request" else None

    req_id = f"req_{uuid4().hex[:8]}"
    card = RequirementCard(
        id=req_id,
        title=request.title,
        priority=request.priority,
        kind=kind,
        project_id=project_id,
    )
    saved = store.requirements.save(card)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=saved.id,
        action="created",
    )
    return saved


@router.get("/{req_id}")
async def get_requirement(workspace: str, req_id: str) -> RequirementCard:
    """Get a specific requirement by ID."""
    store = _get_workspace(workspace)
    try:
        return store.requirements.get(req_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Requirement not found")


@router.post("/{req_id}/transition")
async def transition_requirement_status(
    workspace: str,
    req_id: str,
    request: TransitionRequirementRequest,
) -> RequirementCard:
    """Transition a requirement to a new status."""
    from studio.domain.requirement_flow import transition_requirement

    store = _get_workspace(workspace)
    requirement = store.requirements.get(req_id)

    try:
        updated = transition_requirement(requirement, request.next_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    saved = store.requirements.save(updated)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=saved.id,
        action="updated",
    )
    return saved


@router.get("/{req_id}/delivery-summary")
async def get_requirement_delivery_summary(
    workspace: str,
    req_id: str,
) -> dict:
    """Get aggregated delivery progress for a requirement."""
    store = _get_workspace(workspace)

    try:
        store.requirements.get(req_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Requirement not found")

    all_plans = store.delivery_plans.list_all()
    plans = [p for p in all_plans if p.requirement_id == req_id]
    plan_ids = {p.id for p in plans}

    all_tasks = store.delivery_tasks.list_all()
    tasks = [t for t in all_tasks if t.plan_id in plan_ids]

    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "done")
    in_progress = sum(1 for t in tasks if t.status == "in_progress")
    ready = sum(1 for t in tasks if t.status == "ready")
    blocked = sum(1 for t in tasks if t.status == "blocked")

    latest_plan_status = None
    if plans:
        plans_sorted = sorted(plans, key=lambda p: p.created_at, reverse=True)
        latest_plan_status = plans_sorted[0].status

    return {
        "requirement_id": req_id,
        "plan_count": len(plans),
        "tasks": {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "ready": ready,
            "blocked": blocked,
        },
        "latest_plan_status": latest_plan_status,
    }
