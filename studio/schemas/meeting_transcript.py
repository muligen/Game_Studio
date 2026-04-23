from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


MeetingTranscriptEventKind = Literal["llm"]


class MeetingTranscriptEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    agent_role: StrippedNonEmptyStr
    node_name: StrippedNonEmptyStr
    kind: MeetingTranscriptEventKind = "llm"
    message: StrippedNonEmptyStr
    prompt: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    reply: Any = None


class MeetingTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    events: list[MeetingTranscriptEvent] = Field(default_factory=list)
