from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from studio.schemas.requirement import RequirementCard, RequirementStatus
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/requirements", tags=["requirements"])


class CreateRequirementRequest(BaseModel):
    """Request model for creating a requirement."""

    title: str
    priority: str = "medium"


class TransitionRequirementRequest(BaseModel):
    """Request model for transitioning a requirement status."""

    next_status: RequirementStatus


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance, ensuring it exists."""
    workspace_path = Path(workspace) / ".studio-data"
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

    req_id = f"req_{uuid4().hex[:8]}"
    card = RequirementCard(
        id=req_id,
        title=request.title,
        priority=request.priority,  # type: ignore
    )
    return store.requirements.save(card)


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

    return store.requirements.save(updated)
