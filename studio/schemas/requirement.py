from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


RequirementType = Literal["requirement"]
RequirementKind = Literal["product_mvp", "change_request"]
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
    kind: RequirementKind = "product_mvp"
    type: RequirementType = "requirement"
    priority: RequirementPriority = "medium"
    status: RequirementStatus = "draft"
    owner: StrippedNonEmptyStr = "design_agent"
    design_doc_id: StrippedNonEmptyStr | None = None
    balance_table_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    bug_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
