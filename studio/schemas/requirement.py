from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class RequirementCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    type: StrippedNonEmptyStr = "requirement"
    priority: StrippedNonEmptyStr = "medium"
    status: StrippedNonEmptyStr = "draft"
    owner: StrippedNonEmptyStr = "design_agent"
    design_doc_id: StrippedNonEmptyStr | None = None
    balance_table_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    bug_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
