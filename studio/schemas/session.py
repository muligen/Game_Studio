from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


SessionStatus = Literal["active", "expired"]


class ProjectAgentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    project_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    session_id: StrippedNonEmptyStr
    status: SessionStatus = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_used_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = f"{self.project_id}_{self.agent}"
