from __future__ import annotations

from pydantic import BaseModel


class KickoffTask(BaseModel):
    id: str
    session_id: str
    requirement_id: str
    workspace: str
    project_id: str
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None
    meeting_result: dict | None = None
