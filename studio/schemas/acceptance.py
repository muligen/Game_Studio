from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


AcceptanceSeverity = Literal["blocker", "major", "minor"]
AcceptanceEvidenceType = Literal["command", "playwright", "console", "pageerror", "screenshot", "video", "file", "llm"]
AcceptanceCriterionStatus = Literal["passed", "failed", "inconclusive"]
AcceptanceRunStatus = Literal["running", "passed", "failed", "needs_attention"]
AcceptanceOwnerHint = Literal["dev", "art", "qa", "reviewer", "quality"]


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    source: StrippedNonEmptyStr
    text: StrippedNonEmptyStr
    required_evidence_types: list[AcceptanceEvidenceType] = Field(default_factory=list)
    severity: AcceptanceSeverity = "major"
    owner_hint: AcceptanceOwnerHint = "qa"


class AcceptanceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    criteria: list[AcceptanceCriterion]
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class AcceptanceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    evidence_type: AcceptanceEvidenceType
    summary: StrippedNonEmptyStr
    artifact_path: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class AcceptanceCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: StrippedNonEmptyStr
    status: AcceptanceCriterionStatus
    evidence_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    reason: StrippedNonEmptyStr
    repair_hint: str | None = None
    owner_hint: AcceptanceOwnerHint = "qa"
    blocking: bool = True


class AcceptanceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    contract_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    attempt_number: int = 1
    status: AcceptanceRunStatus = "running"
    evidence: list[AcceptanceEvidence] = Field(default_factory=list)
    criteria_results: list[AcceptanceCriterionResult] = Field(default_factory=list)
    repair_task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
