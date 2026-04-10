from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ArtifactRecord(BaseModel):
    artifact_id: str
    artifact_type: str
    version: int = 1
    source_node: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parent_artifact_id: str | None = None
    review_status: str = "pending"
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)
