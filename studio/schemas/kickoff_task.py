from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KickoffTask(BaseModel):
    id: str
    session_id: str
    requirement_id: str
    workspace: str
    project_id: str
    status: str = "pending"  # pending | running | completed | failed
    error: str | None = None
    meeting_result: dict | None = None
    current_node: str | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    active_agents: list[str] = Field(default_factory=list)
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    started_at: str | None = None
    updated_at: str | None = None
