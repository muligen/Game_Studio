from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _normalize_workspace_path(workspace: str) -> Path:
    raw = Path(workspace)
    if raw.is_absolute():
        return raw
    return (_REPO_ROOT / raw).resolve()


def resolve_workspace_root(workspace: str) -> Path:
    raw = _normalize_workspace_path(workspace)
    if raw.name == ".studio-data":
        return raw
    return raw / ".studio-data"


def resolve_project_root(workspace: str) -> Path:
    raw = _normalize_workspace_path(workspace)
    if raw.name == ".studio-data":
        return raw.parent
    return raw
