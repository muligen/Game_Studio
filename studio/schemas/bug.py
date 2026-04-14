from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class BugCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    severity: StrippedNonEmptyStr
    status: StrippedNonEmptyStr
    reopen_count: int = Field(default=0, ge=0)
    owner: StrippedNonEmptyStr
    repro_steps: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
