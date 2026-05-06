from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


DeliveryTaskEventType = Literal[
    "task_started",
    "agent_session_attached",
    "agent_invocation_started",
    "agent_invocation_completed",
    "file_changes_detected",
    "task_completed",
    "task_failed",
    "task_retried",
]


class DeliveryTaskEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    task_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    event_type: DeliveryTaskEventType
    message: StrippedNonEmptyStr
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
