from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from studio.schemas.artifact import StrippedNonEmptyStr


class BalanceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    table_name: StrippedNonEmptyStr
    columns: list[StrippedNonEmptyStr] = Field(default_factory=list)
    rows: list[list[JsonValue]] = Field(default_factory=list)
    locked_cells: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: StrippedNonEmptyStr
