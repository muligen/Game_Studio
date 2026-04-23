from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr

ClarificationStatus = Literal["collecting", "ready", "kickoff_started", "completed", "failed"]


class ClarificationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: StrippedNonEmptyStr
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class MeetingContextDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: StrippedNonEmptyStr = "pending"
    goals: list[StrippedNonEmptyStr] = Field(default_factory=list)
    constraints: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    risks: list[StrippedNonEmptyStr] = Field(default_factory=list)
    references: list[StrippedNonEmptyStr] = Field(default_factory=list)
    validated_attendees: list[Literal["design", "art", "dev", "qa"]] = Field(default_factory=list)


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RequirementClarificationSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    status: ClarificationStatus = "collecting"
    messages: list[ClarificationMessage] = Field(default_factory=list)
    meeting_context: MeetingContextDraft | None = None
    readiness: ReadinessCheck | None = None
    project_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
