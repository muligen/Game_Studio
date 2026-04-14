from __future__ import annotations

from pydantic import BaseModel


class WorkspaceParam(BaseModel):
    """Common workspace parameter for API requests."""

    workspace: str
