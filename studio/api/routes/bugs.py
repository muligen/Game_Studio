from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studio.api.websocket import broadcast_entity_changed
from studio.schemas.bug import BugCard, BugSeverity, BugStatus
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/bugs", tags=["bugs"])


class CreateBugRequest(BaseModel):
    """Request model for creating a bug."""

    requirement_id: str
    title: str
    severity: BugSeverity
    owner: str = "qa_agent"


class TransitionBugRequest(BaseModel):
    """Request model for transitioning a bug status."""

    next_status: BugStatus


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance, ensuring it exists."""
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_bugs(workspace: str) -> list[BugCard]:
    """List all bugs in the workspace."""
    store = _get_workspace(workspace)
    return store.bugs.list_all()


@router.post("")
async def create_bug(
    workspace: str,
    request: CreateBugRequest,
) -> BugCard:
    """Create a new bug."""
    from uuid import uuid4

    store = _get_workspace(workspace)
    store.ensure_layout()

    bug_id = f"bug_{uuid4().hex[:8]}"
    bug = BugCard(
        id=bug_id,
        requirement_id=request.requirement_id,
        title=request.title,
        severity=request.severity,
        owner=request.owner,
    )
    saved = store.bugs.save(bug)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="bug",
        entity_id=saved.id,
        action="created",
    )
    return saved


@router.get("/{bug_id}")
async def get_bug(workspace: str, bug_id: str) -> BugCard:
    """Get a specific bug by ID."""
    store = _get_workspace(workspace)
    try:
        return store.bugs.get(bug_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Bug not found")


@router.post("/{bug_id}/transition")
async def transition_bug_status(
    workspace: str,
    bug_id: str,
    request: TransitionBugRequest,
) -> BugCard:
    """Transition a bug to a new status."""
    from studio.domain.bug_flow import transition_bug

    store = _get_workspace(workspace)
    bug = store.bugs.get(bug_id)

    try:
        updated = transition_bug(bug, request.next_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    saved = store.bugs.save(updated)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="bug",
        entity_id=saved.id,
        action="updated",
    )
    return saved
