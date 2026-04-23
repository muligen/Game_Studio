from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from studio.api.workspace_paths import resolve_workspace_root
from studio.schemas.action_log import ActionLog
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/logs", tags=["logs"])


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance."""
    workspace_path = resolve_workspace_root(workspace)
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_logs(
    workspace: str,
    limit: int = 100,
) -> list[ActionLog]:
    """List action logs, most recent first."""
    store = _get_workspace(workspace)
    all_logs = store.logs.list_all()
    # Return in reverse order (newest first)
    return list(reversed(all_logs))[:limit]
