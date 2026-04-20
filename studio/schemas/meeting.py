from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class AgentOpinion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_role: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    proposals: list[StrippedNonEmptyStr] = Field(default_factory=list)
    risks: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)


MeetingStatus = Literal["draft", "completed"]


class MeetingMinutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    agenda: list[StrippedNonEmptyStr] = Field(default_factory=list)
    attendees: list[StrippedNonEmptyStr] = Field(default_factory=list)
    opinions: list[AgentOpinion] = Field(default_factory=list)
    consensus_points: list[StrippedNonEmptyStr] = Field(default_factory=list)
    conflict_points: list[StrippedNonEmptyStr] = Field(default_factory=list)
    supplementary: dict[str, str] = Field(default_factory=dict)
    decisions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    action_items: list[StrippedNonEmptyStr] = Field(default_factory=list)
    pending_user_decisions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: MeetingStatus = "draft"
