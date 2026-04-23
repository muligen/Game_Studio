from __future__ import annotations

from pathlib import Path


def resolve_workspace_root(workspace: str) -> Path:
    raw = Path(workspace)
    if raw.name == ".studio-data":
        return raw
    return raw / ".studio-data"


def resolve_project_root(workspace: str) -> Path:
    raw = Path(workspace)
    if raw.name == ".studio-data":
        return raw.parent
    return raw
