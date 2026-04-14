from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue

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
