from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


RequirementType = Literal["requirement"]
RequirementPriority = Literal["low", "medium", "high"]
RequirementStatus = Literal[
    "draft",
    "designing",
    "pending_user_review",
    "approved",
    "implementing",
    "self_test_passed",
    "testing",
    "pending_user_acceptance",
    "quality_check",
    "done",
]


class RequirementCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    type: RequirementType = "requirement"
    priority: RequirementPriority = "medium"
    status: RequirementStatus = "draft"
    owner: StrippedNonEmptyStr = "design_agent"
    design_doc_id: StrippedNonEmptyStr | None = None
    balance_table_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    bug_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
