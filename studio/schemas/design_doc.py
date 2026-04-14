from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class DesignDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    core_rules: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: StrippedNonEmptyStr = "draft"
