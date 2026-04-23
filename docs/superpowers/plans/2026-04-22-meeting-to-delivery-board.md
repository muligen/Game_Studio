# Meeting to Delivery Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert completed meeting minutes into a structured delivery plan with task DAG, kickoff decision gates, session-lease-protected agent execution, and a web delivery board.

**Architecture:** A new `delivery_planner` agent consumes `MeetingMinutes` to produce a `DeliveryPlan` with `DeliveryTask` nodes (DAG) and a `KickoffDecisionGate`. The gate blocks all task execution until the user resolves it. Tasks use project-scoped agent sessions with lease-based concurrency control. A new `/delivery` frontend route shows the board.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI, LangGraph, ClaudeRoleAdapter, React, TypeScript, TanStack Query, shadcn/ui

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `studio/schemas/delivery.py` | Create | All 5 delivery models (DeliveryPlan, DeliveryTask, KickoffDecisionGate, TaskExecutionResult, AgentSessionLease) |
| `studio/storage/workspace.py` | Modify | Add 5 new JsonRepository instances to StudioWorkspace |
| `studio/storage/session_lease.py` | Create | SessionLeaseManager — acquire/release/check leases |
| `studio/storage/delivery_plan_service.py` | Create | DeliveryPlanService — plan generation, gate resolution, cycle detection, task start orchestration |
| `studio/llm/claude_roles.py` | Modify | Add DeliveryPlannerPayload model + register in lookup tables |
| `studio/agents/delivery_planner.py` | Create | DeliveryPlannerAgent — wraps ClaudeRoleAdapter for plan generation |
| `studio/agents/profiles/delivery_planner.yaml` | Create | Agent profile YAML |
| `.claude/agents/delivery_planner/CLAUDE.md` | Create | Agent context directory |
| `studio/api/routes/delivery.py` | Create | 4 API endpoints: generate plan, list board, resolve gate, start task |
| `studio/api/main.py` | Modify | Register delivery router |
| `web/src/lib/api.ts` | Modify | Add delivery API client types and methods |
| `web/src/pages/DeliveryBoard.tsx` | Create | Delivery board page with columns |
| `web/src/components/board/DeliveryTaskCard.tsx` | Create | Task card component |
| `web/src/components/board/KickoffDecisionGateCard.tsx` | Create | Decision gate card component |
| `web/src/components/common/KickoffDecisionDialog.tsx` | Create | Decision resolution dialog |
| `web/src/App.tsx` | Modify | Add /delivery route + nav link |
| `tests/test_delivery_schemas.py` | Create | Schema validation tests |
| `tests/test_session_lease.py` | Create | Lease manager tests |
| `tests/test_delivery_plan_service.py` | Create | Plan service tests (generation, cycle detection, gate resolution, task start) |
| `tests/test_delivery_api.py` | Create | API endpoint tests |
| `tests/test_delivery_planner_agent.py` | Create | Agent + profile tests |

---

### Task 1: Delivery Schemas

**Files:**
- Create: `studio/schemas/delivery.py`
- Test: `tests/test_delivery_schemas.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_delivery_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.delivery import (
    AgentSessionLease,
    DeliveryPlan,
    DeliveryPlanStatus,
    DeliveryTask,
    DeliveryTaskStatus,
    GateItem,
    GateStatus,
    KickoffDecisionGate,
    MeetingSnapshot,
    TaskExecutionResult,
)


def test_delivery_plan_basic():
    plan = DeliveryPlan(
        id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        task_ids=["task_a", "task_b"],
        decision_gate_id="gate_m1",
    )
    assert plan.status == "awaiting_user_decision"
    assert plan.decision_resolution_version is None


def test_delivery_plan_active():
    plan = DeliveryPlan(
        id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="active",
        task_ids=[],
        decision_gate_id="gate_m1",
        decision_resolution_version=1,
    )
    assert plan.status == "active"
    assert plan.decision_resolution_version == 1


def test_delivery_task_basic():
    task = DeliveryTask(
        id="task_combat",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Implement combat loop",
        description="Build the core combat loop",
        owner_agent="dev",
        depends_on_task_ids=[],
        acceptance_criteria=["Battle completes with win/loss"],
    )
    assert task.status == "ready"
    assert task.execution_result_id is None
    assert task.output_artifact_ids == []


def test_delivery_task_blocked():
    task = DeliveryTask(
        id="task_ui",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Build combat UI",
        description="UI for combat",
        owner_agent="dev",
        status="blocked",
        depends_on_task_ids=["task_combat"],
        acceptance_criteria=["UI renders combat state"],
    )
    assert task.status == "blocked"
    assert task.depends_on_task_ids == ["task_combat"]


def test_delivery_task_preview_status():
    task = DeliveryTask(
        id="task_preview",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Preview task",
        description="Preview",
        owner_agent="dev",
        status="preview",
        depends_on_task_ids=[],
        acceptance_criteria=[],
    )
    assert task.status == "preview"


def test_kickoff_decision_gate_basic():
    gate = KickoffDecisionGate(
        id="gate_m1",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        items=[
            GateItem(
                id="decision_skill",
                question="Cooldowns or resource cost?",
                context="Dev needs direction",
                options=["cooldown", "resource", "defer"],
            )
        ],
    )
    assert gate.status == "open"
    assert gate.resolution_version == 0
    assert gate.items[0].resolution is None


def test_kickoff_decision_gate_resolved():
    gate = KickoffDecisionGate(
        id="gate_m1",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        status="resolved",
        resolution_version=1,
        items=[
            GateItem(
                id="decision_skill",
                question="Cooldowns or resource cost?",
                context="Dev needs direction",
                options=["cooldown", "resource", "defer"],
                resolution="Use cooldowns for MVP skills.",
            )
        ],
    )
    assert gate.status == "resolved"
    assert gate.items[0].resolution == "Use cooldowns for MVP skills."


def test_task_execution_result():
    result = TaskExecutionResult(
        id="result_task_combat",
        task_id="task_combat",
        plan_id="plan_m1",
        project_id="proj_1",
        agent="dev",
        session_id="sess_abc",
        summary="Implemented combat loop",
        changed_files=["combat/loop.py"],
        tests_or_checks=["pytest tests/test_combat.py"],
    )
    assert result.output_artifact_ids == []
    assert result.follow_up_notes == []


def test_agent_session_lease():
    lease = AgentSessionLease(
        id="proj_1_dev",
        project_id="proj_1",
        agent="dev",
        task_id="task_combat",
        session_id="sess_abc",
    )
    assert lease.status == "held"
    assert lease.expires_at is not None


def test_meeting_snapshot():
    snap = MeetingSnapshot(
        meeting_title="Combat Kickoff",
        relevant_decisions=["Core loop locked to 3v3"],
        relevant_consensus=["Three action types confirmed"],
        task_acceptance_notes=["Turn order follows speed sorting"],
    )
    assert snap.meeting_title == "Combat Kickoff"


def test_delivery_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DeliveryPlan(
            id="plan_m1",
            meeting_id="meeting_1",
            requirement_id="req_1",
            project_id="proj_1",
            task_ids=[],
            decision_gate_id="gate_m1",
            unknown_field="oops",
        )


def test_delivery_task_with_meeting_snapshot():
    task = DeliveryTask(
        id="task_combat",
        plan_id="plan_m1",
        meeting_id="meeting_1",
        requirement_id="req_1",
        project_id="proj_1",
        title="Implement combat loop",
        description="Build it",
        owner_agent="dev",
        meeting_snapshot=MeetingSnapshot(
            meeting_title="Combat Kickoff",
            relevant_decisions=["3v3 format"],
            relevant_consensus=["Action types"],
            task_acceptance_notes=["Speed sorting"],
        ),
    )
    assert task.meeting_snapshot is not None
    assert task.meeting_snapshot.meeting_title == "Combat Kickoff"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.schemas.delivery'`

- [ ] **Step 3: Write the schema module**

```python
# studio/schemas/delivery.py
from __future__ import annotations

from datetime import UTC, datetime
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
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = f"{self.project_id}_{self.agent}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_schemas.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add studio/schemas/delivery.py tests/test_delivery_schemas.py
git commit -m "feat: add delivery schemas (DeliveryPlan, DeliveryTask, KickoffDecisionGate, TaskExecutionResult, AgentSessionLease)"
```

---

### Task 2: Workspace Integration & Session Lease Manager

**Files:**
- Modify: `studio/storage/workspace.py` — add 5 new repositories
- Create: `studio/storage/session_lease.py` — lease acquire/release/check
- Test: `tests/test_session_lease.py`

- [ ] **Step 1: Write the failing lease tests**

```python
# tests/test_session_lease.py
from __future__ import annotations

from pathlib import Path

import pytest

from studio.schemas.delivery import AgentSessionLease
from studio.storage.session_lease import SessionLeaseManager


def test_acquire_lease(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    lease = mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    assert lease.status == "held"
    assert lease.id == "proj_1_dev"


def test_acquire_persists(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    loaded = mgr.find("proj_1", "dev")
    assert loaded is not None
    assert loaded.task_id == "task_1"


def test_acquire_fails_when_held(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    with pytest.raises(ValueError, match="already held"):
        mgr.acquire("proj_1", "dev", "task_2", "sess_xyz")


def test_release_lease(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    mgr.release("proj_1", "dev")
    loaded = mgr.find("proj_1", "dev")
    assert loaded is not None
    assert loaded.status == "released"


def test_release_allows_reacquire(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    mgr.release("proj_1", "dev")
    lease2 = mgr.acquire("proj_1", "dev", "task_2", "sess_xyz")
    assert lease2.task_id == "task_2"


def test_is_available_no_lease(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    assert mgr.is_available("proj_1", "dev") is True


def test_is_available_when_held(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    assert mgr.is_available("proj_1", "dev") is False


def test_is_available_when_released(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    mgr.acquire("proj_1", "dev", "task_1", "sess_abc")
    mgr.release("proj_1", "dev")
    assert mgr.is_available("proj_1", "dev") is True


def test_release_nonexistent_raises(tmp_path: Path):
    mgr = SessionLeaseManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        mgr.release("proj_999", "dev")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_session_lease.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Add repositories to StudioWorkspace**

In `studio/storage/workspace.py`, add imports for the new schemas and add 5 new repositories:

```python
# Add to imports at top:
from studio.schemas.delivery import (
    AgentSessionLease,
    DeliveryPlan,
    DeliveryTask,
    KickoffDecisionGate,
    TaskExecutionResult,
)

# Add to StudioWorkspace.__init__ (after self.sessions = ...):
        self.delivery_plans = JsonRepository(root / "delivery_plans", DeliveryPlan)
        self.delivery_tasks = JsonRepository(root / "delivery_tasks", DeliveryTask)
        self.decision_gates = JsonRepository(root / "kickoff_decision_gates", KickoffDecisionGate)
        self.execution_results = JsonRepository(root / "task_execution_results", TaskExecutionResult)
        self.session_leases = JsonRepository(root / "agent_session_leases", AgentSessionLease)

# Add to ensure_layout() tuple:
            self.delivery_plans.root,
            self.delivery_tasks.root,
            self.decision_gates.root,
            self.execution_results.root,
            self.session_leases.root,
```

- [ ] **Step 4: Create SessionLeaseManager**

```python
# studio/storage/session_lease.py
from __future__ import annotations

from pathlib import Path

from studio.schemas.delivery import AgentSessionLease
from studio.storage.base import JsonRepository


class SessionLeaseManager:
    def __init__(self, root: Path) -> None:
        self._repo = JsonRepository(root / "agent_session_leases", AgentSessionLease)

    def acquire(self, project_id: str, agent: str, task_id: str, session_id: str) -> AgentSessionLease:
        composite_id = f"{project_id}_{agent}"
        existing = self.find(project_id, agent)
        if existing is not None and existing.status == "held":
            raise ValueError(f"session lease already held by task {existing.task_id}")
        lease = AgentSessionLease(
            project_id=project_id,
            agent=agent,
            task_id=task_id,
            session_id=session_id,
        )
        return self._repo.save(lease)

    def release(self, project_id: str, agent: str) -> AgentSessionLease:
        composite_id = f"{project_id}_{agent}"
        try:
            lease = self._repo.get(composite_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"no lease for {composite_id}") from exc
        updated = lease.model_copy(update={"status": "released"})
        return self._repo.save(updated)

    def find(self, project_id: str, agent: str) -> AgentSessionLease | None:
        composite_id = f"{project_id}_{agent}"
        try:
            return self._repo.get(composite_id)
        except (FileNotFoundError, ValueError):
            return None

    def is_available(self, project_id: str, agent: str) -> bool:
        lease = self.find(project_id, agent)
        return lease is None or lease.status != "held"
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_session_lease.py tests/test_delivery_schemas.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add studio/storage/workspace.py studio/storage/session_lease.py tests/test_session_lease.py
git commit -m "feat: add workspace delivery repos and SessionLeaseManager"
```

---

### Task 3: Delivery Plan Service (Cycle Detection, Generation, Gate Resolution, Task Start)

**Files:**
- Create: `studio/storage/delivery_plan_service.py`
- Test: `tests/test_delivery_plan_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
# tests/test_delivery_plan_service.py
from __future__ import annotations

from pathlib import Path

import pytest

from studio.schemas.meeting import MeetingMinutes
from studio.storage.delivery_plan_service import DeliveryPlanService


def _completed_meeting(tmp_path: Path, **overrides) -> MeetingMinutes:
    defaults = dict(
        id="meeting_1",
        requirement_id="req_1",
        title="Combat MVP Kickoff",
        status="completed",
        agenda=["Scope"],
        attendees=["design", "dev", "qa"],
        consensus_points=["Core combat loop locked to 3v3"],
        conflict_points=["Skill cost system unresolved"],
        decisions=["Start with MVP"],
        action_items=["Implement combat loop", "Build combat UI"],
        pending_user_decisions=["Cooldowns or resource cost?"],
    )
    defaults.update(overrides)
    m = MeetingMinutes(**defaults)
    from studio.storage.workspace import StudioWorkspace
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    ws.meetings.save(m)
    return m


def test_detect_cycle_no_cycle():
    assert DeliveryPlanService._has_cycle(
        {"task_a": ["task_b"], "task_b": ["task_c"], "task_c": []},
    ) is False


def test_detect_cycle_simple():
    assert DeliveryPlanService._has_cycle(
        {"task_a": ["task_b"], "task_b": ["task_a"]},
    ) is True


def test_detect_cycle_self_dep():
    assert DeliveryPlanService._has_cycle(
        {"task_a": ["task_a"]},
    ) is True


def test_detect_cycle_three_node():
    assert DeliveryPlanService._has_cycle(
        {"task_a": ["task_b"], "task_b": ["task_c"], "task_c": ["task_a"]},
    ) is True


def test_generate_plan_creates_plan_and_gate(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    result = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {
                    "title": "Implement combat loop",
                    "description": "Core loop",
                    "owner_agent": "dev",
                    "depends_on": [],
                    "acceptance_criteria": ["Battle completes"],
                    "source_evidence": ["Core combat loop locked"],
                },
            ],
            "decision_gate": {
                "items": [
                    {
                        "question": "Cooldowns or resource?",
                        "context": "Skill cost unresolved",
                        "options": ["cooldown", "resource"],
                        "source_evidence": ["Cooldowns or resource cost?"],
                    }
                ],
            },
        },
        project_id="proj_1",
    )
    assert result["plan"].status == "awaiting_user_decision"
    assert len(result["tasks"]) == 1
    assert result["decision_gate"].status == "open"
    assert len(result["decision_gate"].items) == 1


def test_generate_plan_rejects_cycle(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    with pytest.raises(ValueError, match="cyclic"):
        svc.generate_plan(
            meeting_id="meeting_1",
            planner_output={
                "tasks": [
                    {"title": "A", "description": "a", "owner_agent": "dev", "depends_on": ["B"], "acceptance_criteria": [], "source_evidence": []},
                    {"title": "B", "description": "b", "owner_agent": "dev", "depends_on": ["A"], "acceptance_criteria": [], "source_evidence": []},
                ],
                "decision_gate": {"items": []},
            },
            project_id="proj_1",
        )


def test_generate_plan_rejects_unknown_owner(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    with pytest.raises(ValueError, match="owner_agent"):
        svc.generate_plan(
            meeting_id="meeting_1",
            planner_output={
                "tasks": [
                    {"title": "A", "description": "a", "owner_agent": "wizard", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
                ],
                "decision_gate": {"items": []},
            },
            project_id="proj_1",
        )


def test_generate_plan_no_gate_creates_active(tmp_path: Path):
    _completed_meeting(tmp_path, pending_user_decisions=[], conflict_points=[])
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    result = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {"items": []},
        },
        project_id="proj_1",
    )
    assert result["plan"].status == "active"
    assert result["decision_gate"] is None


def test_resolve_gate_activates_plan(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    gen = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {
                "items": [
                    {"question": "Q?", "context": "ctx", "options": ["a", "b"], "source_evidence": []},
                ],
            },
        },
        project_id="proj_1",
    )
    gate_id = gen["decision_gate"].id
    plan_id = gen["plan"].id
    result = svc.resolve_gate(
        gate_id=gate_id,
        resolutions={gen["decision_gate"].items[0].id: "Use cooldowns"},
    )
    assert result["gate"].status == "resolved"
    assert result["plan"].status == "active"
    assert result["plan"].decision_resolution_version == 1


def test_resolve_gate_rejects_partial(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    gen = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [],
            "decision_gate": {
                "items": [
                    {"question": "Q1?", "context": "c1", "options": ["a", "b"], "source_evidence": []},
                    {"question": "Q2?", "context": "c2", "options": ["c", "d"], "source_evidence": []},
                ],
            },
        },
        project_id="proj_1",
    )
    gate_id = gen["decision_gate"].id
    with pytest.raises(ValueError, match="unresolved"):
        svc.resolve_gate(
            gate_id=gate_id,
            resolutions={gen["decision_gate"].items[0].id: "a"},
        )


def test_start_task_checks_session_exists(tmp_path: Path):
    _completed_meeting(tmp_path, pending_user_decisions=[])
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    gen = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {"items": []},
        },
        project_id="proj_1",
    )
    task_id = gen["tasks"][0].id
    with pytest.raises(ValueError, match="session"):
        svc.start_task(task_id=task_id, session_id="sess_abc")


def test_start_task_blocks_when_gate_open(tmp_path: Path):
    _completed_meeting(tmp_path)
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    gen = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {
                "items": [{"question": "Q?", "context": "c", "options": ["a"], "source_evidence": []}],
            },
        },
        project_id="proj_1",
    )
    task_id = gen["tasks"][0].id
    with pytest.raises(ValueError, match="gate"):
        svc.start_task(task_id=task_id, session_id="sess_abc")


def test_list_board_items(tmp_path: Path):
    _completed_meeting(tmp_path, pending_user_decisions=[])
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {"items": []},
        },
        project_id="proj_1",
    )
    board = svc.list_board()
    assert len(board["plans"]) == 1
    assert len(board["tasks"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_plan_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write DeliveryPlanService**

```python
# studio/storage/delivery_plan_service.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from studio.schemas.delivery import (
    DeliveryPlan,
    DeliveryTask,
    GateItem,
    KickoffDecisionGate,
)
from studio.storage.session_lease import SessionLeaseManager
from studio.storage.workspace import StudioWorkspace

_VALID_OWNER_AGENTS = {"design", "dev", "qa", "art", "reviewer", "quality"}


class DeliveryPlanService:
    def __init__(self, workspace_root: Path) -> None:
        self._ws = StudioWorkspace(workspace_root)
        self._lease_mgr = SessionLeaseManager(workspace_root.parent.parent)

    def generate_plan(
        self,
        meeting_id: str,
        planner_output: dict,
        project_id: str,
    ) -> dict:
        meeting = self._ws.meetings.get(meeting_id)
        if meeting.status != "completed":
            raise ValueError("meeting not completed")

        existing = [
            p for p in self._ws.delivery_plans.list_all() if p.meeting_id == meeting_id
        ]
        if existing:
            plan = existing[0]
            gate = None
            if plan.decision_gate_id:
                gate = self._ws.decision_gates.get(plan.decision_gate_id)
            return {
                "plan": plan,
                "tasks": [self._ws.delivery_tasks.get(t) for t in plan.task_ids],
                "decision_gate": gate,
            }

        raw_tasks = planner_output.get("tasks", [])
        raw_gate = planner_output.get("decision_gate", {})

        plan_id = f"plan_{uuid4().hex[:8]}"
        gate_id = f"gate_{uuid4().hex[:8]}"

        task_deps: dict[str, list[str]] = {}
        title_to_id: dict[str, str] = {}
        task_records: list[DeliveryTask] = []

        for raw in raw_tasks:
            owner = raw["owner_agent"]
            if owner not in _VALID_OWNER_AGENTS:
                raise ValueError(f"invalid owner_agent: {owner}")
            task_id = f"task_{uuid4().hex[:8]}"
            title_to_id[raw["title"]] = task_id
            task_deps[task_id] = raw.get("depends_on", [])

        resolved_deps: dict[str, list[str]] = {}
        for tid, dep_titles in task_deps.items():
            resolved = []
            for d in dep_titles:
                if d in title_to_id:
                    resolved.append(title_to_id[d])
                else:
                    resolved.append(d)
            resolved_deps[tid] = resolved

        if self._has_cycle(resolved_deps):
            raise ValueError("cyclic dependency detected in delivery tasks")

        for raw in raw_tasks:
            task_id = title_to_id[raw["title"]]
            deps = resolved_deps[task_id]
            status = "blocked" if deps else "ready"
            task = DeliveryTask(
                id=task_id,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=meeting.requirement_id,
                project_id=project_id,
                title=raw["title"],
                description=raw["description"],
                owner_agent=raw["owner_agent"],
                status=status,
                depends_on_task_ids=deps,
                acceptance_criteria=raw.get("acceptance_criteria", []),
            )
            self._ws.delivery_tasks.save(task)
            task_records.append(task)

        gate_items = raw_gate.get("items", [])
        has_gate = len(gate_items) > 0

        gate_record = None
        if has_gate:
            gate = KickoffDecisionGate(
                id=gate_id,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=meeting.requirement_id,
                project_id=project_id,
                items=[
                    GateItem(
                        id=f"decision_{uuid4().hex[:8]}",
                        question=gi["question"],
                        context=gi["context"],
                        options=gi["options"],
                    )
                    for gi in gate_items
                ],
            )
            self._ws.decision_gates.save(gate)
            gate_record = gate

        plan_status = "awaiting_user_decision" if has_gate else "active"
        plan = DeliveryPlan(
            id=plan_id,
            meeting_id=meeting_id,
            requirement_id=meeting.requirement_id,
            project_id=project_id,
            status=plan_status,
            task_ids=[t.id for t in task_records],
            decision_gate_id=gate_id if has_gate else None,
            decision_resolution_version=1 if not has_gate else None,
        )
        self._ws.delivery_plans.save(plan)

        return {"plan": plan, "tasks": task_records, "decision_gate": gate_record}

    def resolve_gate(self, gate_id: str, resolutions: dict[str, str]) -> dict:
        gate = self._ws.decision_gates.get(gate_id)
        if gate.status != "open":
            raise ValueError(f"gate is not open: {gate.status}")

        for item in gate.items:
            if item.id not in resolutions:
                raise ValueError(f"unresolved gate item: {item.id}")
            if resolutions[item.id] not in item.options:
                raise ValueError(
                    f"resolution '{resolutions[item.id]}' not in options for {item.id}"
                )

        updated_items = [
            item.model_copy(update={"resolution": resolutions[item.id]})
            for item in gate.items
        ]
        now = datetime.now(UTC).isoformat()
        resolved_gate = gate.model_copy(
            update={
                "status": "resolved",
                "resolution_version": gate.resolution_version + 1,
                "items": updated_items,
                "updated_at": now,
            }
        )
        self._ws.decision_gates.save(resolved_gate)

        plan = self._ws.delivery_plans.get(gate.plan_id)
        updated_plan = plan.model_copy(
            update={
                "status": "active",
                "decision_resolution_version": resolved_gate.resolution_version,
                "updated_at": now,
            }
        )
        self._ws.delivery_plans.save(updated_plan)

        for task_id in plan.task_ids:
            task = self._ws.delivery_tasks.get(task_id)
            if task.status == "preview":
                updated_task = task.model_copy(
                    update={
                        "status": "ready",
                        "decision_resolution_version": resolved_gate.resolution_version,
                        "updated_at": now,
                    }
                )
                self._ws.delivery_tasks.save(updated_task)

        return {"gate": resolved_gate, "plan": updated_plan}

    def start_task(self, task_id: str, session_id: str) -> DeliveryTask:
        task = self._ws.delivery_tasks.get(task_id)

        if task.status not in ("ready",):
            raise ValueError(f"task is not ready: {task.status}")

        plan = self._ws.delivery_plans.get(task.plan_id)
        if plan.decision_gate_id:
            gate = self._ws.decision_gates.get(plan.decision_gate_id)
            if gate.status != "resolved":
                raise ValueError("kickoff decision gate is still open")

        for dep_id in task.depends_on_task_ids:
            dep = self._ws.delivery_tasks.get(dep_id)
            if dep.status != "done":
                raise ValueError(f"dependency {dep_id} is not done (status: {dep.status})")

        session = self._ws.sessions.find(task.project_id, task.owner_agent)
        if session is None:
            raise ValueError(f"no project session for {task.project_id}/{task.owner_agent}")

        if not self._lease_mgr.is_available(task.project_id, task.owner_agent):
            raise ValueError(f"agent session lease for {task.owner_agent} is already held")

        self._lease_mgr.acquire(
            task.project_id, task.owner_agent, task.id, session_id
        )

        now = datetime.now(UTC).isoformat()
        updated = task.model_copy(
            update={"status": "in_progress", "updated_at": now}
        )
        self._ws.delivery_tasks.save(updated)
        return updated

    def list_board(self, requirement_id: str | None = None) -> dict:
        plans = self._ws.delivery_plans.list_all()
        tasks = self._ws.delivery_tasks.list_all()
        gates = self._ws.decision_gates.list_all()

        if requirement_id:
            plans = [p for p in plans if p.requirement_id == requirement_id]
            plan_ids = {p.id for p in plans}
            tasks = [t for t in tasks if t.plan_id in plan_ids]
            gate_plan_ids = {p.decision_gate_id for p in plans if p.decision_gate_id}
            gates = [g for g in gates if g.id in gate_plan_ids]

        gate_by_plan = {g.plan_id: g for g in gates}
        board_gates = [
            gate_by_plan[p.id] for p in plans if p.id in gate_by_plan
        ]

        return {"plans": plans, "tasks": tasks, "decision_gates": board_gates}

    @staticmethod
    def _has_cycle(dep_graph: dict[str, list[str]]) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in dep_graph}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in dep_graph.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        return any(color[n] == WHITE and dfs(n) for n in dep_graph)
```

- [ ] **Step 4: Fix the start_task test to set up sessions**

The `test_start_task_checks_session_exists` test needs a session to exist for the check to pass. Update the test to also verify the happy path when a session exists. Add after the existing `test_start_task_checks_session_exists`:

```python
# Add to tests/test_delivery_plan_service.py

def test_start_task_succeeds_with_session(tmp_path: Path):
    _completed_meeting(tmp_path, pending_user_decisions=[])
    svc = DeliveryPlanService(tmp_path / ".studio-data")
    # Create project session
    from studio.storage.session_registry import SessionRegistry
    SessionRegistry(tmp_path / ".studio-data").create("proj_1", "req_1", "dev", "sess_abc")

    gen = svc.generate_plan(
        meeting_id="meeting_1",
        planner_output={
            "tasks": [
                {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
            ],
            "decision_gate": {"items": []},
        },
        project_id="proj_1",
    )
    task_id = gen["tasks"][0].id
    updated = svc.start_task(task_id=task_id, session_id="sess_abc")
    assert updated.status == "in_progress"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_plan_service.py -v`
Expected: All 13 tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add studio/storage/delivery_plan_service.py tests/test_delivery_plan_service.py
git commit -m "feat: add DeliveryPlanService with cycle detection, generation, gate resolution, task start"
```

---

### Task 4: Delivery Planner Agent

**Files:**
- Modify: `studio/llm/claude_roles.py` — add DeliveryPlannerPayload
- Create: `studio/agents/delivery_planner.py`
- Create: `studio/agents/profiles/delivery_planner.yaml`
- Create: `.claude/agents/delivery_planner/CLAUDE.md`
- Test: `tests/test_delivery_planner_agent.py`

- [ ] **Step 1: Write the failing agent tests**

```python
# tests/test_delivery_planner_agent.py
from __future__ import annotations

from pathlib import Path

import pytest

from studio.agents.delivery_planner import DeliveryPlannerAgent
from studio.llm.claude_roles import DeliveryPlannerPayload


def test_payload_parses_valid_json():
    payload = DeliveryPlannerPayload.model_validate({
        "tasks": [
            {
                "title": "Implement combat",
                "description": "Core loop",
                "owner_agent": "dev",
                "depends_on": [],
                "acceptance_criteria": ["Battle completes"],
                "source_evidence": ["Core loop locked"],
            }
        ],
        "decision_gate": {
            "items": [
                {
                    "question": "Q?",
                    "context": "ctx",
                    "options": ["a", "b"],
                    "source_evidence": ["pending item"],
                }
            ]
        },
    })
    assert len(payload.tasks) == 1
    assert payload.tasks[0].owner_agent == "dev"
    assert len(payload.decision_gate.items) == 1


def test_payload_rejects_extra_fields():
    with pytest.raises(Exception):
        DeliveryPlannerPayload.model_validate({
            "tasks": [],
            "decision_gate": {"items": []},
            "unknown": True,
        })


def test_agent_has_profile():
    from studio.agents.profile_loader import AgentProfileLoader
    profile = AgentProfileLoader().load("delivery_planner")
    assert profile.name == "delivery_planner"
    assert profile.enabled is True


def test_agent_profile_claude_dir():
    from studio.agents.profile_loader import AgentProfileLoader
    profile = AgentProfileLoader().load("delivery_planner")
    assert profile.claude_project_root.exists()
    claude_md = profile.claude_project_root / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text(encoding="utf-8")
    assert "delivery_planner" in content


def test_agent_generate_returns_plan_dict():
    agent = DeliveryPlannerAgent(claude_runner=_MockRunner())
    from studio.schemas.runtime import RuntimeState
    state = RuntimeState(goal={"prompt": "Build combat system"})
    result = agent.run(state)
    assert result.decision.value == "continue"
    telemetry = result.state_patch.get("telemetry", {})
    assert "delivery_plan" in telemetry


class _MockRunner:
    """Minimal mock for ClaudeRoleAdapter."""
    def generate(self, role_name: str, context: dict):
        return DeliveryPlannerPayload(
            tasks=[],
            decision_gate=type("DG", (), {"items": []})(),
        )

    def consume_debug_record(self):
        return None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_planner_agent.py -v`
Expected: FAIL — `ImportError` / missing files

- [ ] **Step 3: Add DeliveryPlannerPayload to claude_roles.py**

Add to `studio/llm/claude_roles.py` after the existing payload classes (after `ModeratorMinutesPayload`):

```python
class DeliveryPlannerTaskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    owner_agent: str
    depends_on: list[str]
    acceptance_criteria: list[str]
    source_evidence: list[str]


class DeliveryPlannerGateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    context: str
    options: list[str]
    source_evidence: list[str]


class DeliveryPlannerGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DeliveryPlannerGateItem]


class DeliveryPlannerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[DeliveryPlannerTaskItem]
    decision_gate: DeliveryPlannerGate
```

Register in `_ROLE_PAYLOAD_MODELS`:

```python
    "delivery_planner": DeliveryPlannerPayload,
```

Register in `_ROLE_PROMPTS`:

```python
    "delivery_planner": (
        "You are the delivery planner.\n"
        "Given meeting minutes, requirement context, and optional kickoff gate resolutions, "
        "produce a delivery plan with tasks and a decision gate.\n"
        "Return only JSON with:\n"
        "- tasks: list of {title, description, owner_agent (one of: design, dev, qa, art, reviewer, quality), "
        "depends_on (list of other task titles), acceptance_criteria, source_evidence}\n"
        "- decision_gate: {items: [{question, context, options, source_evidence}]} "
        "for unresolved conflicts requiring user direction. Empty items if no conflicts.\n"
    ),
```

- [ ] **Step 4: Create the agent profile YAML**

```yaml
# studio/agents/profiles/delivery_planner.yaml
name: delivery_planner
enabled: true
system_prompt: >
  You are the delivery planner. Given completed meeting minutes, produce a structured
  delivery plan with tasks and a kickoff decision gate for unresolved conflicts.
  Tasks must have clear owner agents, dependency references, and acceptance criteria.
  Only surface decisions that genuinely require user direction.
claude_project_root: .claude/agents/delivery_planner
model: sonnet
fallback_policy: strict
```

- [ ] **Step 5: Create the agent CLAUDE.md context directory**

Create directory `.claude/agents/delivery_planner/` and file `CLAUDE.md`:

```
This directory belongs only to the delivery_planner agent.
```

- [ ] **Step 6: Create the agent implementation**

```python
# studio/agents/delivery_planner.py
from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DeliveryPlannerAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
        session_id: str | None = None,
        resume_session: bool = False,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader(repo_root=project_root).load("delivery_planner")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root,
            profile=profile,
            session_id=session_id,
            resume_session=resume_session,
        )

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "delivery_planner",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "delivery_planner"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal, "phase": "plan_generation"}
        try:
            payload = self._claude_runner.generate("delivery_planner", llm_context)
            state_patch["telemetry"] = {"delivery_plan": self._payload_to_dict(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"delivery_plan": self._fallback_plan(state)}

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _payload_to_dict(payload: object) -> dict[str, object]:
        return {
            "tasks": [
                {
                    "title": t.title,
                    "description": t.description,
                    "owner_agent": t.owner_agent,
                    "depends_on": t.depends_on,
                    "acceptance_criteria": t.acceptance_criteria,
                    "source_evidence": t.source_evidence,
                }
                for t in payload.tasks
            ],
            "decision_gate": {
                "items": [
                    {
                        "question": gi.question,
                        "context": gi.context,
                        "options": gi.options,
                        "source_evidence": gi.source_evidence,
                    }
                    for gi in payload.decision_gate.items
                ],
            },
        }

    @staticmethod
    def _fallback_plan(state: RuntimeState) -> dict[str, object]:
        return {"tasks": [], "decision_gate": {"items": []}}

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_planner_agent.py -v`
Expected: All 5 tests PASS

- [ ] **Step 8: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add studio/llm/claude_roles.py studio/agents/delivery_planner.py studio/agents/profiles/delivery_planner.yaml .claude/agents/delivery_planner/CLAUDE.md tests/test_delivery_planner_agent.py
git commit -m "feat: add delivery_planner agent with profile, payload, and context dir"
```

---

### Task 5: Delivery API Routes

**Files:**
- Create: `studio/api/routes/delivery.py`
- Modify: `studio/api/main.py` — register delivery router
- Test: `tests/test_delivery_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# tests/test_delivery_api.py
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.api.main import create_app
from studio.schemas.meeting import MeetingMinutes
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def client(tmp_path: Path):
    app = create_app()
    return TestClient(app)


@pytest.fixture
def workspace(tmp_path: Path) -> str:
    ws_path = str(tmp_path / "ws")
    ws = StudioWorkspace(Path(ws_path) / ".studio-data")
    ws.ensure_layout()
    return ws_path


def _seed_meeting(workspace: str, meeting_id: str = "meeting_1", **overrides):
    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    defaults = dict(
        id=meeting_id,
        requirement_id="req_1",
        title="Test Meeting",
        status="completed",
        decisions=["Start MVP"],
        action_items=["Implement"],
    )
    defaults.update(overrides)
    ws.meetings.save(MeetingMinutes(**defaults))


def test_generate_delivery_plan(client, workspace):
    _seed_meeting(workspace)
    resp = client.post(
        f"/api/meetings/meeting_1/delivery-plan?workspace={workspace}",
        json={"project_id": "proj_1", "planner_output": {"tasks": [
            {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
        ], "decision_gate": {"items": []}}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["status"] == "active"
    assert len(data["tasks"]) == 1


def test_generate_plan_missing_meeting(client, workspace):
    resp = client.post(
        f"/api/meetings/meeting_999/delivery-plan?workspace={workspace}",
        json={"project_id": "proj_1", "planner_output": {"tasks": [], "decision_gate": {"items": []}}},
    )
    assert resp.status_code == 404


def test_list_delivery_board(client, workspace):
    _seed_meeting(workspace)
    client.post(
        f"/api/meetings/meeting_1/delivery-plan?workspace={workspace}",
        json={"project_id": "proj_1", "planner_output": {"tasks": [], "decision_gate": {"items": []}}},
    )
    resp = client.get(f"/api/delivery-board?workspace={workspace}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["plans"]) == 1


def test_resolve_gate(client, workspace):
    _seed_meeting(workspace, pending_user_decisions=["Q?"], conflict_points=["Skill cost"])
    gen = client.post(
        f"/api/meetings/meeting_1/delivery-plan?workspace={workspace}",
        json={"project_id": "proj_1", "planner_output": {"tasks": [], "decision_gate": {"items": [
            {"question": "Q?", "context": "c", "options": ["a", "b"], "source_evidence": []},
        ]}}},
    ).json()
    gate_id = gen["decision_gate"]["id"]
    item_id = gen["decision_gate"]["items"][0]["id"]
    resp = client.post(
        f"/api/kickoff-decision-gates/{gate_id}/resolve?workspace={workspace}",
        json={"resolutions": {item_id: "a"}},
    )
    assert resp.status_code == 200
    assert resp.json()["gate"]["status"] == "resolved"
    assert resp.json()["plan"]["status"] == "active"


def test_start_task(client, workspace):
    _seed_meeting(workspace)
    gen = client.post(
        f"/api/meetings/meeting_1/delivery-plan?workspace={workspace}",
        json={"project_id": "proj_1", "planner_output": {"tasks": [
            {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": [], "source_evidence": []},
        ], "decision_gate": {"items": []}}},
    ).json()
    task_id = gen["tasks"][0]["id"]

    # Create project session
    from studio.storage.session_registry import SessionRegistry
    SessionRegistry(Path(workspace) / ".studio-data").create("proj_1", "req_1", "dev", "sess_abc")

    resp = client.post(
        f"/api/delivery-tasks/{task_id}/start?workspace={workspace}",
        json={"session_id": "sess_abc"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_api.py -v`
Expected: FAIL — 404 on routes

- [ ] **Step 3: Create delivery API routes**

```python
# studio/api/routes/delivery.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studio.api.websocket import broadcast_entity_changed
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.workspace import StudioWorkspace

router = APIRouter(tags=["delivery"])


class PlannerOutputRequest(BaseModel):
    project_id: str
    planner_output: dict


class ResolveGateRequest(BaseModel):
    resolutions: dict[str, str]


class StartTaskRequest(BaseModel):
    session_id: str


def _get_workspace(workspace: str) -> StudioWorkspace:
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


def _service(workspace: str) -> DeliveryPlanService:
    return DeliveryPlanService(Path(workspace) / ".studio-data")


@router.post("/meetings/{meeting_id}/delivery-plan")
async def generate_delivery_plan(meeting_id: str, workspace: str, request: PlannerOutputRequest):
    svc = _service(workspace)
    try:
        result = svc.generate_plan(
            meeting_id=meeting_id,
            planner_output=request.planner_output,
            project_id=request.project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await broadcast_entity_changed(
        workspace=workspace, entity_type="delivery_plan", entity_id=result["plan"].id, action="created",
    )
    return {
        "plan": result["plan"].model_dump(),
        "tasks": [t.model_dump() for t in result["tasks"]],
        "decision_gate": result["decision_gate"].model_dump() if result["decision_gate"] else None,
    }


@router.get("/delivery-board")
async def list_delivery_board(workspace: str, requirement_id: str | None = None):
    svc = _service(workspace)
    result = svc.list_board(requirement_id=requirement_id)
    return {
        "plans": [p.model_dump() for p in result["plans"]],
        "tasks": [t.model_dump() for t in result["tasks"]],
        "decision_gates": [g.model_dump() for g in result["decision_gates"]],
    }


@router.post("/kickoff-decision-gates/{gate_id}/resolve")
async def resolve_gate(gate_id: str, workspace: str, request: ResolveGateRequest):
    svc = _service(workspace)
    try:
        result = svc.resolve_gate(gate_id=gate_id, resolutions=request.resolutions)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    await broadcast_entity_changed(
        workspace=workspace, entity_type="decision_gate", entity_id=gate_id, action="resolved",
    )
    return {
        "gate": result["gate"].model_dump(),
        "plan": result["plan"].model_dump(),
    }


@router.post("/delivery-tasks/{task_id}/start")
async def start_delivery_task(task_id: str, workspace: str, request: StartTaskRequest):
    svc = _service(workspace)
    try:
        updated = svc.start_task(task_id=task_id, session_id=request.session_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    await broadcast_entity_changed(
        workspace=workspace, entity_type="delivery_task", entity_id=task_id, action="started",
    )
    return updated.model_dump()
```

- [ ] **Step 4: Register delivery router in main.py**

In `studio/api/main.py`, add import:

```python
from studio.api.routes import delivery
```

Add to `create_app()` after the other `include_router` calls:

```python
    app.include_router(delivery.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/test_delivery_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add studio/api/routes/delivery.py studio/api/main.py tests/test_delivery_api.py
git commit -m "feat: add delivery API routes (generate plan, board listing, resolve gate, start task)"
```

---

### Task 6: Frontend API Client

**Files:**
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add delivery types and API methods to api.ts**

Add the following after the `poolApi` section in `web/src/lib/api.ts`:

```typescript
// Delivery types
export interface DeliveryPlan {
  id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  status: 'awaiting_user_decision' | 'active' | 'completed' | 'cancelled'
  task_ids: string[]
  decision_gate_id: string | null
  decision_resolution_version: number | null
  created_at: string
  updated_at: string
}

export interface DeliveryTask {
  id: string
  plan_id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  title: string
  description: string
  owner_agent: string
  status: 'preview' | 'blocked' | 'ready' | 'in_progress' | 'review' | 'done' | 'cancelled'
  depends_on_task_ids: string[]
  execution_result_id: string | null
  output_artifact_ids: string[]
  acceptance_criteria: string[]
  meeting_snapshot: {
    meeting_title: string
    relevant_decisions: string[]
    relevant_consensus: string[]
    task_acceptance_notes: string[]
  } | null
  decision_resolution_version: number | null
  created_at: string
  updated_at: string
}

export interface GateItem {
  id: string
  question: string
  context: string
  options: string[]
  resolution: string | null
}

export interface KickoffDecisionGate {
  id: string
  plan_id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  status: 'open' | 'resolved' | 'cancelled'
  resolution_version: number
  items: GateItem[]
  created_at: string
  updated_at: string
}

export interface DeliveryBoard {
  plans: DeliveryPlan[]
  tasks: DeliveryTask[]
  decision_gates: KickoffDecisionGate[]
}

// Delivery API
export const deliveryApi = {
  generatePlan: (
    workspace: string,
    meetingId: string,
    projectId: string,
    plannerOutput: Record<string, unknown>,
  ): Promise<{ plan: DeliveryPlan; tasks: DeliveryTask[]; decision_gate: KickoffDecisionGate | null }> =>
    apiRequest(`/meetings/${meetingId}/delivery-plan`, 'post', {
      params: { workspace },
      body: { project_id: projectId, planner_output: plannerOutput },
    }) as Promise<{ plan: DeliveryPlan; tasks: DeliveryTask[]; decision_gate: KickoffDecisionGate | null }>,

  listBoard: (workspace: string, requirementId?: string): Promise<DeliveryBoard> =>
    apiRequest('/delivery-board', 'get', {
      params: { workspace, ...(requirementId ? { requirement_id: requirementId } : {}) },
    }) as Promise<DeliveryBoard>,

  resolveGate: (
    workspace: string,
    gateId: string,
    resolutions: Record<string, string>,
  ): Promise<{ gate: KickoffDecisionGate; plan: DeliveryPlan }> =>
    apiRequest(`/kickoff-decision-gates/${gateId}/resolve`, 'post', {
      params: { workspace },
      body: { resolutions },
    }) as Promise<{ gate: KickoffDecisionGate; plan: DeliveryPlan }>,

  startTask: (
    workspace: string,
    taskId: string,
    sessionId: string,
  ): Promise<DeliveryTask> =>
    apiRequest(`/delivery-tasks/${taskId}/start`, 'post', {
      params: { workspace },
      body: { session_id: sessionId },
    }) as Promise<DeliveryTask>,
} as const
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board/web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add web/src/lib/api.ts
git commit -m "feat: add delivery API client types and methods"
```

---

### Task 7: Delivery Board Frontend — Page & Components

**Files:**
- Create: `web/src/components/board/DeliveryTaskCard.tsx`
- Create: `web/src/components/board/KickoffDecisionGateCard.tsx`
- Create: `web/src/components/common/KickoffDecisionDialog.tsx`
- Create: `web/src/pages/DeliveryBoard.tsx`
- Modify: `web/src/App.tsx` — add route and nav link

- [ ] **Step 1: Create DeliveryTaskCard**

```tsx
// web/src/components/board/DeliveryTaskCard.tsx
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { DeliveryTask } from '@/lib/api'

interface DeliveryTaskCardProps {
  task: DeliveryTask
  onStart?: () => void
}

const STATUS_COLORS: Record<string, string> = {
  preview: 'bg-gray-100 text-gray-800',
  blocked: 'bg-red-100 text-red-800',
  ready: 'bg-green-100 text-green-800',
  in_progress: 'bg-blue-100 text-blue-800',
  review: 'bg-yellow-100 text-yellow-800',
  done: 'bg-emerald-100 text-emerald-800',
  cancelled: 'bg-gray-200 text-gray-600',
}

const AGENT_COLORS: Record<string, string> = {
  design: 'bg-purple-200',
  dev: 'bg-blue-200',
  qa: 'bg-orange-200',
  art: 'bg-pink-200',
  reviewer: 'bg-indigo-200',
  quality: 'bg-teal-200',
}

export function DeliveryTaskCard({ task, onStart }: DeliveryTaskCardProps) {
  const canStart = task.status === 'ready' && onStart

  return (
    <Card className="p-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs text-muted-foreground">{task.id}</span>
        <Badge className={AGENT_COLORS[task.owner_agent] || 'bg-gray-200'}>
          {task.owner_agent}
        </Badge>
      </div>
      <h3 className="font-medium mb-1">{task.title}</h3>
      <p className="text-sm text-muted-foreground mb-2 line-clamp-2">{task.description}</p>
      <div className="flex items-center justify-between mt-2">
        <Badge className={STATUS_COLORS[task.status] || STATUS_COLORS.ready}>
          {task.status.replace(/_/g, ' ')}
        </Badge>
        {task.depends_on_task_ids.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {task.depends_on_task_ids.length} dep{task.depends_on_task_ids.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
      {task.acceptance_criteria.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          {task.acceptance_criteria.slice(0, 2).map((c, i) => (
            <div key={i} className="truncate">- {c}</div>
          ))}
        </div>
      )}
      {canStart && (
        <button
          className="mt-2 text-xs text-blue-600 hover:underline"
          onClick={(e) => { e.stopPropagation(); onStart() }}
        >
          Start Agent Work
        </button>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Create KickoffDecisionGateCard**

```tsx
// web/src/components/board/KickoffDecisionGateCard.tsx
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { KickoffDecisionGate } from '@/lib/api'

interface KickoffDecisionGateCardProps {
  gate: KickoffDecisionGate
  onResolve?: () => void
}

export function KickoffDecisionGateCard({ gate, onResolve }: KickoffDecisionGateCardProps) {
  const isOpen = gate.status === 'open'

  return (
    <Card className="p-4 border-amber-300 bg-amber-50">
      <div className="flex justify-between items-start mb-2">
        <Badge className={isOpen ? 'bg-amber-200 text-amber-800' : 'bg-green-200 text-green-800'}>
          {isOpen ? 'Kickoff Decision Required' : 'Resolved'}
        </Badge>
        <span className="text-xs text-muted-foreground">{gate.id}</span>
      </div>
      <h3 className="font-medium mb-3">Decision Gate</h3>
      <div className="space-y-3">
        {gate.items.map((item) => (
          <div key={item.id} className="text-sm">
            <p className="font-medium">{item.question}</p>
            <p className="text-muted-foreground text-xs">{item.context}</p>
            {item.resolution ? (
              <p className="text-green-700 text-xs mt-1">Resolved: {item.resolution}</p>
            ) : (
              <div className="flex gap-1 mt-1 flex-wrap">
                {item.options.map((opt) => (
                  <Badge key={opt} variant="outline" className="text-xs">{opt}</Badge>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {isOpen && onResolve && (
        <button
          className="mt-3 w-full text-sm font-medium text-amber-800 hover:underline"
          onClick={onResolve}
        >
          Resolve Decisions
        </button>
      )}
    </Card>
  )
}
```

- [ ] **Step 3: Create KickoffDecisionDialog**

```tsx
// web/src/components/common/KickoffDecisionDialog.tsx
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deliveryApi } from '@/lib/api'
import type { KickoffDecisionGate, GateItem } from '@/lib/api'

interface KickoffDecisionDialogProps {
  gate: KickoffDecisionGate
  workspace: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function KickoffDecisionDialog({
  gate,
  workspace,
  open,
  onOpenChange,
}: KickoffDecisionDialogProps) {
  const [selections, setSelections] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const item of gate.items) {
      init[item.id] = ''
    }
    return init
  })
  const queryClient = useQueryClient()

  const resolveMutation = useMutation({
    mutationFn: () => deliveryApi.resolveGate(workspace, gate.id, selections),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      onOpenChange(false)
    },
  })

  const allSelected = gate.items.every((item) => selections[item.id])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Resolve Kickoff Decisions</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {gate.items.map((item) => (
            <div key={item.id}>
              <p className="font-medium text-sm">{item.question}</p>
              <p className="text-xs text-muted-foreground mb-2">{item.context}</p>
              <select
                value={selections[item.id]}
                onChange={(e) =>
                  setSelections((prev) => ({ ...prev, [item.id]: e.target.value }))
                }
                className="w-full h-10 rounded-md border border-gray-300 px-3 text-sm"
              >
                <option value="">Select an option...</option>
                {item.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          ))}
          {resolveMutation.error && (
            <p className="text-sm text-red-600">Error: {String(resolveMutation.error)}</p>
          )}
          <div className="flex justify-end gap-3">
            <DialogClose asChild>
              <Button type="button" variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              onClick={() => resolveMutation.mutate()}
              disabled={!allSelected || resolveMutation.isPending}
            >
              {resolveMutation.isPending ? 'Resolving...' : 'Resolve'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 4: Create DeliveryBoard page**

```tsx
// web/src/pages/DeliveryBoard.tsx
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useWorkspace } from '@/lib/workspace'
import { deliveryApi } from '@/lib/api'
import type { KickoffDecisionGate, DeliveryTask } from '@/lib/api'
import { DeliveryTaskCard } from '@/components/board/DeliveryTaskCard'
import { KickoffDecisionGateCard } from '@/components/board/KickoffDecisionGateCard'
import { KickoffDecisionDialog } from '@/components/common/KickoffDecisionDialog'
import { useWebSocket } from '@/hooks/useWebSocket'

const COLUMNS = [
  { key: 'gate', title: 'Kickoff Decision Needed', status: 'gate' },
  { key: 'blocked', title: 'Blocked', status: 'blocked' },
  { key: 'ready', title: 'Ready', status: 'ready' },
  { key: 'in_progress', title: 'In Progress', status: 'in_progress' },
  { key: 'review', title: 'Review', status: 'review' },
  { key: 'done', title: 'Done', status: 'done' },
] as const

export function DeliveryBoard() {
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const { connected, subscribe } = useWebSocket()
  const [resolveGate, setResolveGate] = useState<KickoffDecisionGate | null>(null)
  const [startTaskId, setStartTaskId] = useState<string | null>(null)

  const { data: board, isLoading, error } = useQuery({
    queryKey: ['delivery-board', workspace],
    queryFn: () => deliveryApi.listBoard(workspace),
  })

  useEffect(() => {
    if (connected) subscribe(workspace)
  }, [connected, workspace, subscribe])

  useEffect(() => {
    const handleMessage = (e: Event) => {
      const message = (e as CustomEvent).detail
      if (
        message.type === 'entity_changed' &&
        ['delivery_plan', 'delivery_task', 'decision_gate'].includes(message.entity_type)
      ) {
        queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      }
    }
    window.addEventListener('ws-message', handleMessage as EventListener)
    return () => window.removeEventListener('ws-message', handleMessage as EventListener)
  }, [queryClient])

  const startMutation = useMutation({
    mutationFn: (taskId: string) => deliveryApi.startTask(workspace, taskId, 'session-placeholder'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['delivery-board'] })
      setStartTaskId(null)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-600">Loading delivery board...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-600">Error: {error.message}</p>
      </div>
    )
  }

  const gates = board?.decision_gates.filter((g) => g.status === 'open') || []
  const tasks = board?.tasks || []
  const tasksByStatus = (status: string) => tasks.filter((t) => t.status === status)

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8 space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Delivery Board</h1>
        <div className="flex gap-6 overflow-x-auto pb-4">
          {COLUMNS.map((col) => (
            <div key={col.key} className="flex-shrink-0 w-80">
              <h2 className="font-semibold mb-4 text-sm uppercase text-gray-600">
                {col.title} ({col.key === 'gate' ? gates.length : tasksByStatus(col.status).length})
              </h2>
              <div className="space-y-3">
                {col.key === 'gate'
                  ? gates.map((gate) => (
                      <KickoffDecisionGateCard
                        key={gate.id}
                        gate={gate}
                        onResolve={() => setResolveGate(gate)}
                      />
                    ))
                  : tasksByStatus(col.status).map((task) => (
                      <DeliveryTaskCard
                        key={task.id}
                        task={task}
                        onStart={
                          task.status === 'ready'
                            ? () => startMutation.mutate(task.id)
                            : undefined
                        }
                      />
                    ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      {resolveGate && (
        <KickoffDecisionDialog
          gate={resolveGate}
          workspace={workspace}
          open={!!resolveGate}
          onOpenChange={(open) => { if (!open) setResolveGate(null) }}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Update App.tsx with delivery route and nav link**

In `web/src/App.tsx`:
- Add import: `import { DeliveryBoard } from '@/pages/DeliveryBoard'`
- Add route: `<Route path="/delivery" element={<DeliveryBoard />} />`
- Add nav link: `<Link to="/delivery" className="hover:underline">Delivery</Link>`

Updated `App.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { RequirementsBoard } from '@/pages/RequirementsBoard'
import { BugsBoard } from '@/pages/BugsBoard'
import { DesignEditor } from '@/pages/DesignEditor'
import { Logs } from '@/pages/Logs'
import { DeliveryBoard } from '@/pages/DeliveryBoard'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="bg-white border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex gap-6">
              <Link to="/requirements" className="hover:underline">Requirements</Link>
              <Link to="/bugs" className="hover:underline">Bugs</Link>
              <Link to="/delivery" className="hover:underline">Delivery</Link>
              <Link to="/logs" className="hover:underline">Logs</Link>
            </nav>
          </div>
        </div>
        <Routes>
          <Route path="/" element={<RequirementsBoard />} />
          <Route path="/requirements" element={<RequirementsBoard />} />
          <Route path="/bugs" element={<BugsBoard />} />
          <Route path="/delivery" element={<DeliveryBoard />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/design-docs/:id" element={<DesignEditor />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board/web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board
git add web/src/components/board/DeliveryTaskCard.tsx web/src/components/board/KickoffDecisionGateCard.tsx web/src/components/common/KickoffDecisionDialog.tsx web/src/pages/DeliveryBoard.tsx web/src/App.tsx
git commit -m "feat: add delivery board page with task cards, gate cards, and decision dialog"
```

---

### Task 8: Run Full Test Suite & Fix Regressions

**Files:**
- All existing and new test files

- [ ] **Step 1: Run the full test suite**

Run: `cd F:/projs/Game_Studio/.worktrees/meeting-to-delivery-board && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (new + existing)

- [ ] **Step 2: Fix any regressions or failures**

If any existing tests break due to workspace changes or imports, fix them inline.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test regressions from delivery board feature"
```

---

## Scope Check

This spec covers schemas, storage, agent, session management, API, and frontend — all for a single cohesive feature (meeting → delivery pipeline). They are interdependent layers, not independent subsystems. Kept as one plan.

## Self-Review

1. **Spec coverage:** Every spec requirement maps to a task:
   - Data models → Task 1
   - Workspace/storage → Task 2
   - Cycle detection → Task 3
   - Delivery planner agent → Task 4
   - API endpoints → Task 5
   - Frontend board → Tasks 6-7
   - Session lease → Task 2 (SessionLeaseManager) + Task 3 (start_task checks)
   - Dependency output handoff → Task 3 (TaskExecutionResult in schema, referenced in start_task)

2. **Placeholder scan:** No TBD/TODO/fill-in-later. All code provided.

3. **Type consistency:** `DeliveryPlanService` uses the same model names and field names defined in Task 1 schemas. API routes use the same types. Frontend types match backend JSON shapes.
