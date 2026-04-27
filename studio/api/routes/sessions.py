from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from studio.api.workspace_paths import resolve_workspace_root
from studio.storage.session_lease import SessionLeaseManager
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/project/{project_id}")
async def list_sessions(project_id: str, workspace: str) -> dict:
    """List all agent sessions for a project."""
    ws = StudioWorkspace(resolve_workspace_root(workspace))
    ws.ensure_layout()
    sessions = [s for s in ws.sessions.list_all() if s.project_id == project_id]
    return {
        "project_id": project_id,
        "sessions": [s.model_dump() for s in sessions],
    }


@router.get("")
async def list_all_sessions(workspace: str) -> dict:
    """List all agent sessions across projects."""
    ws = StudioWorkspace(resolve_workspace_root(workspace))
    ws.ensure_layout()
    sessions = ws.sessions.list_all()
    return {
        "sessions": [s.model_dump() for s in sessions],
    }


@router.get("/{session_composite_id}/status")
async def get_session_status(session_composite_id: str, workspace: str) -> dict:
    """Get session status including whether the agent is busy (lease held)."""
    ws = StudioWorkspace(resolve_workspace_root(workspace))
    ws.ensure_layout()

    try:
        session = ws.sessions.get(session_composite_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    lease_mgr = SessionLeaseManager(resolve_workspace_root(workspace))
    lease = lease_mgr.find(session.project_id, session.agent)
    busy = lease is not None and lease.status == "held"

    return {
        "session": session.model_dump(),
        "busy": busy,
    }
