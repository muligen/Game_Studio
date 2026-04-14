from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class RequirementCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    type: StrippedNonEmptyStr
    priority: StrippedNonEmptyStr
    status: StrippedNonEmptyStr
    owner: StrippedNonEmptyStr
    design_doc_id: StrippedNonEmptyStr
    balance_table_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    bug_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
