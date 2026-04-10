from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from studio.schemas.artifact import ArtifactRecord


class NodeDecision(StrEnum):
    CONTINUE = "continue"
    RETRY = "retry"
    BRANCH = "branch"
    ESCALATE = "escalate"
    STOP = "stop"


class PlanState(BaseModel):
    graph_name: str = "game_studio_demo"
    current_node: str | None = None
    pending_nodes: list[str] = Field(default_factory=list)
    completed_nodes: list[str] = Field(default_factory=list)


class HumanGate(BaseModel):
    gate_id: str
    reason: str
    status: str = "pending"


class RuntimeState(BaseModel):
    project_id: str
    run_id: str
    task_id: str
    goal: dict[str, object]
    plan: PlanState = Field(default_factory=PlanState)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    human_gates: list[HumanGate] = Field(default_factory=list)
    telemetry: dict[str, object] = Field(default_factory=dict)


class NodeResult(BaseModel):
    decision: NodeDecision
    state_patch: dict[str, object] = Field(default_factory=dict)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    trace: dict[str, object] = Field(default_factory=dict)
    typed_error: str | None = None
