from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


DesignDocStatus = Literal["draft", "pending_user_review", "approved", "sent_back"]


class DesignDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    core_rules: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: DesignDocStatus = "draft"
    sent_back_reason: str | None = None
