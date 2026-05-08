from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


AssumptionSource = Literal["meeting", "planner", "agent", "acceptance"]
AssumptionCategory = Literal["product", "art", "tech", "qa", "scope", "delivery"]
AssumptionOwner = Literal["design", "dev", "qa", "art", "reviewer", "quality"]
AssumptionChangePolicy = Literal["next_iteration"]


class ProjectAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    source: AssumptionSource
    category: AssumptionCategory
    decision: StrippedNonEmptyStr
    rationale: StrippedNonEmptyStr
    impact: StrippedNonEmptyStr
    owner_agent: AssumptionOwner
    change_policy: AssumptionChangePolicy = "next_iteration"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ProjectAssumptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: AssumptionCategory
    decision: StrippedNonEmptyStr
    rationale: StrippedNonEmptyStr
    impact: StrippedNonEmptyStr
    owner_agent: AssumptionOwner
    change_policy: AssumptionChangePolicy = "next_iteration"

    def to_assumption(
        self,
        *,
        assumption_id: str,
        requirement_id: str,
        project_id: str,
        source: AssumptionSource,
    ) -> ProjectAssumption:
        return ProjectAssumption(
            id=assumption_id,
            requirement_id=requirement_id,
            project_id=project_id,
            source=source,
            category=self.category,
            decision=self.decision,
            rationale=self.rationale,
            impact=self.impact,
            owner_agent=self.owner_agent,
            change_policy=self.change_policy,
        )


class NeedsAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr | None = None
    blocker: StrippedNonEmptyStr
    evidence: list[StrippedNonEmptyStr] = Field(default_factory=list)
    recommended_action: StrippedNonEmptyStr
    affected_task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    resumable: bool = True
    status: Literal["open", "resolved"] = "open"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
