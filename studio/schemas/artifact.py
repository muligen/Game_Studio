from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, field_validator


def _strip_nonempty_str(v: Any) -> str:
    if not isinstance(v, str):
        raise ValueError("expected str")
    s = v.strip()
    if not s:
        raise ValueError("must not be empty")
    return s


StrippedNonEmptyStr = Annotated[str, BeforeValidator(_strip_nonempty_str)]


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: StrippedNonEmptyStr
    artifact_type: StrippedNonEmptyStr
    version: int = Field(default=1, ge=1)
    source_node: StrippedNonEmptyStr
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parent_artifact_id: StrippedNonEmptyStr | None = None
    review_status: StrippedNonEmptyStr = "pending"
    tags: list[StrippedNonEmptyStr] = Field(default_factory=list)
    payload: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("parent_artifact_id", mode="before")
    @classmethod
    def _parent_optional(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            raise ValueError("parent_artifact_id must not be blank when provided")
        return v
