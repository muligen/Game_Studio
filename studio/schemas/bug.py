from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


BugSeverity = Literal["low", "medium", "high", "critical"]
BugStatus = Literal["new", "fixing", "fixed", "verifying", "closed", "reopened", "needs_user_decision"]


class BugCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    severity: BugSeverity
    status: BugStatus = "new"
    reopen_count: int = Field(default=0, ge=0)
    owner: StrippedNonEmptyStr
    repro_steps: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
