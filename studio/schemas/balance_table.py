from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from studio.schemas.artifact import StrippedNonEmptyStr


WorkflowValue = str | int | float | bool
BalanceTableStatus = Literal["draft", "pending_user_review", "approved", "sent_back"]


class BalanceTableRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[StrippedNonEmptyStr, WorkflowValue]


class BalanceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    table_name: StrippedNonEmptyStr
    columns: list[StrippedNonEmptyStr] = Field(default_factory=list)
    rows: list[BalanceTableRow] = Field(default_factory=list)
    locked_cells: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: BalanceTableStatus = "draft"

    @model_validator(mode="after")
    def _rows_match_columns(self) -> "BalanceTable":
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("columns must not contain duplicates")
        column_set = set(self.columns)
        for row in self.rows:
            extra_keys = set(row.values) - column_set
            if extra_keys:
                raise ValueError(f"row contains unknown columns: {sorted(extra_keys)}")
        return self
