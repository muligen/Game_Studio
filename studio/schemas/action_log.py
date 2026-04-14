from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from studio.schemas.artifact import StrippedNonEmptyStr


class ActionLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    timestamp: datetime
    actor: StrippedNonEmptyStr
    action: StrippedNonEmptyStr
    target_type: StrippedNonEmptyStr
    target_id: StrippedNonEmptyStr
    message: StrippedNonEmptyStr
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(UTC)
