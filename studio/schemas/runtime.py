from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from studio.schemas.artifact import ArtifactRecord, StrippedNonEmptyStr


class NodeDecision(StrEnum):
    CONTINUE = "continue"
    RETRY = "retry"
    BRANCH = "branch"
    ESCALATE = "escalate"
    STOP = "stop"


class PlanState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph_name: StrippedNonEmptyStr = "game_studio_demo"
    current_node: StrippedNonEmptyStr | None = None
    pending_nodes: list[StrippedNonEmptyStr] = Field(default_factory=list)
    completed_nodes: list[StrippedNonEmptyStr] = Field(default_factory=list)

    @field_validator("current_node", mode="before")
    @classmethod
    def _current_node_blank_to_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v


class HumanGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: StrippedNonEmptyStr
    reason: StrippedNonEmptyStr
    status: StrippedNonEmptyStr = "pending"


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: StrippedNonEmptyStr
    run_id: StrippedNonEmptyStr
    task_id: StrippedNonEmptyStr
    goal: dict[str, JsonValue]
    plan: PlanState = Field(default_factory=PlanState)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    memory_refs: list[StrippedNonEmptyStr] = Field(default_factory=list)
    risks: list[StrippedNonEmptyStr] = Field(default_factory=list)
    human_gates: list[HumanGate] = Field(default_factory=list)
    telemetry: dict[str, JsonValue] = Field(default_factory=dict)


class NodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: NodeDecision
    state_patch: dict[str, JsonValue] = Field(default_factory=dict)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    trace: dict[str, JsonValue] = Field(default_factory=dict)
    typed_error: StrippedNonEmptyStr | None = None

    @field_validator("typed_error", mode="before")
    @classmethod
    def _typed_error_blank_to_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v
