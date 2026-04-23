from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


DeliveryPlanStatus = Literal[
    "awaiting_user_decision", "active", "completed", "cancelled",
]

DeliveryTaskStatus = Literal[
    "preview", "blocked", "ready", "in_progress", "review", "done", "cancelled",
]

GateStatus = Literal["open", "resolved", "cancelled"]


class MeetingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meeting_title: StrippedNonEmptyStr
    relevant_decisions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    relevant_consensus: list[StrippedNonEmptyStr] = Field(default_factory=list)
    task_acceptance_notes: list[StrippedNonEmptyStr] = Field(default_factory=list)


class GateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    question: StrippedNonEmptyStr
    context: StrippedNonEmptyStr
    options: list[StrippedNonEmptyStr]
    resolution: str | None = None


class DeliveryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    status: DeliveryPlanStatus = "awaiting_user_decision"
    task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    decision_gate_id: StrippedNonEmptyStr | None = None
    decision_resolution_version: int | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class DeliveryTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    description: StrippedNonEmptyStr
    owner_agent: StrippedNonEmptyStr
    status: DeliveryTaskStatus = "ready"
    depends_on_task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    execution_result_id: StrippedNonEmptyStr | None = None
    output_artifact_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    meeting_snapshot: MeetingSnapshot | None = None
    decision_resolution_version: int | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class KickoffDecisionGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    status: GateStatus = "open"
    resolution_version: int = 0
    items: list[GateItem] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class TaskExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    task_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    session_id: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    output_artifact_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    tests_or_checks: list[str] = Field(default_factory=list)
    follow_up_notes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class AgentSessionLease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    project_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    task_id: StrippedNonEmptyStr
    session_id: StrippedNonEmptyStr
    status: Literal["held", "released"] = "held"
    expires_at: str = Field(
        default_factory=lambda: (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = f"{self.project_id}_{self.agent}"
