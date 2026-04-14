# AI Studio Collaboration Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-first collaboration kernel with structured workflow objects, local JSON persistence, command-style CLI operations, and LangGraph-visible workflow execution for requirement, design, development, QA, and quality flows.

**Architecture:** Keep workflow correctness in a new domain layer, persist entities through filesystem-backed repositories, expose command-style operations through the Typer CLI, and let LangGraph graphs orchestrate agent-driven workflow steps against stored entities. Replace the current demo-only runtime incrementally so tests stay green while the new kernel lands.

**Tech Stack:** Python 3.12, Pydantic v2, Typer, LangGraph, pytest, local JSON file persistence

---

## Planned File Changes

Create:

- `studio/schemas/requirement.py`
- `studio/schemas/design_doc.py`
- `studio/schemas/balance_table.py`
- `studio/schemas/bug.py`
- `studio/schemas/action_log.py`
- `studio/storage/__init__.py`
- `studio/storage/base.py`
- `studio/storage/workspace.py`
- `studio/domain/__init__.py`
- `studio/domain/requirement_flow.py`
- `studio/domain/bug_flow.py`
- `studio/domain/approvals.py`
- `studio/domain/services.py`
- `studio/agents/design.py`
- `studio/agents/dev.py`
- `studio/agents/qa.py`
- `studio/agents/quality.py`
- `studio/agents/art.py`
- `tests/test_workflow_schemas.py`
- `tests/test_workflow_repositories.py`
- `tests/test_requirement_flow.py`
- `tests/test_bug_flow.py`
- `tests/test_approvals.py`
- `tests/test_workflow_cli.py`

Modify:

- `studio/agents/__init__.py`
- `studio/runtime/dispatcher.py`
- `studio/runtime/graph.py`
- `studio/langgraph_app.py`
- `studio/interfaces/cli.py`
- `README.md`
- `tests/test_langgraph_studio.py`

Remove or deprecate after migration:

- demo-only graph assumptions in `tests/test_graph_run.py`

## Task 1: Add Workflow Schema Tests And Models

**Files:**
- Create: `tests/test_workflow_schemas.py`
- Create: `studio/schemas/requirement.py`
- Create: `studio/schemas/design_doc.py`
- Create: `studio/schemas/balance_table.py`
- Create: `studio/schemas/bug.py`
- Create: `studio/schemas/action_log.py`

- [ ] **Step 1: Write the failing schema tests**

```python
from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def test_requirement_card_defaults() -> None:
    card = RequirementCard(id="req_001", title="Add relic system")
    assert card.status == "draft"
    assert card.priority == "medium"
    assert card.design_doc_id is None
    assert card.balance_table_ids == []
    assert card.bug_ids == []
    assert card.notes == []


def test_design_doc_rejects_extra_fields() -> None:
    import pytest

    with pytest.raises(Exception):
        DesignDoc(
            id="design_001",
            requirement_id="req_001",
            title="Relic design",
            summary="Add relics",
            core_rules=[],
            acceptance_criteria=[],
            open_questions=[],
            status="draft",
            extra_field="boom",
        )


def test_bug_card_requires_positive_reopen_count() -> None:
    BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="major",
        status="new",
        reopen_count=-1,
        owner="qa_agent",
        repro_steps=[],
        notes=[],
    )


def test_action_log_tracks_target_and_actor() -> None:
    log = ActionLog(
        id="log_001",
        timestamp="2026-04-14T12:00:00Z",
        actor="user",
        action="approve",
        target_type="design_doc",
        target_id="design_001",
        message="approved design",
        metadata={"status": "approved"},
    )
    assert log.target_id == "design_001"
```

- [ ] **Step 2: Run schema tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_workflow_schemas.py
```

Expected:

- import errors for missing schema modules
- validation assertions failing until models exist

- [ ] **Step 3: Implement workflow schema modules**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from studio.schemas.artifact import StrippedNonEmptyStr


RequirementPriority = Literal["low", "medium", "high"]
RequirementStatus = Literal[
    "draft",
    "designing",
    "pending_user_review",
    "approved",
    "implementing",
    "self_test_passed",
    "testing",
    "pending_user_acceptance",
    "quality_check",
    "done",
]


class RequirementCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    type: StrippedNonEmptyStr = "requirement"
    priority: RequirementPriority = "medium"
    status: RequirementStatus = "draft"
    owner: StrippedNonEmptyStr = "design_agent"
    design_doc_id: StrippedNonEmptyStr | None = None
    balance_table_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    bug_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
```

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


DesignDocStatus = Literal["draft", "pending_user_review", "approved", "sent_back"]


class DesignDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    core_rules: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: DesignDocStatus = "draft"
```

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


BalanceTableStatus = Literal["draft", "pending_user_review", "approved", "sent_back"]


class BalanceTableRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[StrippedNonEmptyStr, str | int | float | bool]


class BalanceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    table_name: StrippedNonEmptyStr
    columns: list[StrippedNonEmptyStr] = Field(default_factory=list)
    rows: list[BalanceTableRow] = Field(default_factory=list)
    locked_cells: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: BalanceTableStatus = "draft"
```

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from studio.schemas.artifact import StrippedNonEmptyStr


BugSeverity = Literal["minor", "major", "critical"]
BugStatus = Literal["new", "fixing", "fixed", "verifying", "closed", "reopened", "needs_user_decision"]


class BugCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    severity: BugSeverity
    status: BugStatus = "new"
    reopen_count: NonNegativeInt = 0
    owner: StrippedNonEmptyStr = "qa_agent"
    repro_steps: list[StrippedNonEmptyStr] = Field(default_factory=list)
    notes: list[StrippedNonEmptyStr] = Field(default_factory=list)
```

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from studio.schemas.artifact import StrippedNonEmptyStr


class ActionLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    timestamp: StrippedNonEmptyStr
    actor: StrippedNonEmptyStr
    action: StrippedNonEmptyStr
    target_type: StrippedNonEmptyStr
    target_id: StrippedNonEmptyStr
    message: StrippedNonEmptyStr
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
```

- [ ] **Step 4: Run schema tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_workflow_schemas.py
```

Expected:

- all schema tests pass

- [ ] **Step 5: Commit**

```batch
git add tests/test_workflow_schemas.py studio/schemas/requirement.py studio/schemas/design_doc.py studio/schemas/balance_table.py studio/schemas/bug.py studio/schemas/action_log.py
git commit -m "feat: add workflow schemas"
```

## Task 2: Add Workspace Repositories And Local Storage Tests

**Files:**
- Create: `tests/test_workflow_repositories.py`
- Create: `studio/storage/__init__.py`
- Create: `studio/storage/base.py`
- Create: `studio/storage/workspace.py`
- Create: `studio/storage/requirements.py`
- Create: `studio/storage/design_docs.py`
- Create: `studio/storage/balance_tables.py`
- Create: `studio/storage/bugs.py`
- Create: `studio/storage/logs.py`

- [ ] **Step 1: Write the failing repository tests**

```python
from pathlib import Path

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def test_workspace_creates_expected_directories(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    workspace.ensure_layout()

    assert (tmp_path / ".studio-data" / "requirements").is_dir()
    assert (tmp_path / ".studio-data" / "design_docs").is_dir()
    assert (tmp_path / ".studio-data" / "bugs").is_dir()


def test_requirement_repository_round_trips_cards(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    repo = workspace.requirements
    card = RequirementCard(id="req_001", title="Add relic system")

    repo.save(card)
    loaded = repo.get("req_001")

    assert loaded.model_dump() == card.model_dump()


def test_log_repository_lists_saved_entries(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    log = workspace.logs.new(
        actor="user",
        action="approve",
        target_type="design_doc",
        target_id="design_001",
        message="approved",
        metadata={},
    )
    workspace.logs.save(log)

    assert [entry.id for entry in workspace.logs.list_all()] == [log.id]
```

- [ ] **Step 2: Run repository tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_workflow_repositories.py
```

Expected:

- missing import errors for workspace and repository modules

- [ ] **Step 3: Implement workspace and repositories**

```python
from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonRepository(Generic[ModelT]):
    def __init__(self, root: Path, model_type: type[ModelT]) -> None:
        self.root = root
        self.model_type = model_type
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, object_id: str) -> Path:
        return self.root / f"{object_id}.json"

    def save(self, model: ModelT) -> ModelT:
        path = self._path_for(str(model.model_dump()["id"]))
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        return model

    def get(self, object_id: str) -> ModelT:
        path = self._path_for(object_id)
        return self.model_type.model_validate_json(path.read_text(encoding="utf-8"))

    def list_all(self) -> list[ModelT]:
        return [
            self.model_type.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]
```

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.base import JsonRepository


class LogRepository(JsonRepository[ActionLog]):
    def new(
        self,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        message: str,
        metadata: dict[str, object],
    ) -> ActionLog:
        timestamp = datetime.now(UTC).isoformat()
        return ActionLog(
            id=f"log_{int(datetime.now(UTC).timestamp() * 1000)}",
            timestamp=timestamp,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            message=message,
            metadata=metadata,
        )


class StudioWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.requirements = JsonRepository(root / "requirements", RequirementCard)
        self.design_docs = JsonRepository(root / "design_docs", DesignDoc)
        self.balance_tables = JsonRepository(root / "balance_tables", BalanceTable)
        self.bugs = JsonRepository(root / "bugs", BugCard)
        self.logs = LogRepository(root / "logs", ActionLog)

    def ensure_layout(self) -> None:
        for repo_root in (
            self.requirements.root,
            self.design_docs.root,
            self.balance_tables.root,
            self.bugs.root,
            self.logs.root,
        ):
            repo_root.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run repository tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_workflow_repositories.py
```

Expected:

- all repository tests pass

- [ ] **Step 5: Commit**

```batch
git add tests/test_workflow_repositories.py studio/storage/__init__.py studio/storage/base.py studio/storage/workspace.py
git commit -m "feat: add workflow repositories"
```

## Task 3: Add Requirement And Bug State Machines

**Files:**
- Create: `tests/test_requirement_flow.py`
- Create: `tests/test_bug_flow.py`
- Create: `studio/domain/requirement_flow.py`
- Create: `studio/domain/bug_flow.py`

- [ ] **Step 1: Write the failing flow tests**

```python
import pytest

from studio.domain.bug_flow import advance_bug, transition_bug
from studio.domain.requirement_flow import transition_requirement
from studio.schemas.bug import BugCard
from studio.schemas.requirement import RequirementCard


def test_requirement_allows_pending_review_to_approved() -> None:
    card = RequirementCard(id="req_001", title="Add relic system", status="pending_user_review")
    updated = transition_requirement(card, "approved")
    assert updated.status == "approved"


def test_requirement_rejects_draft_to_done() -> None:
    card = RequirementCard(id="req_001", title="Add relic system")
    with pytest.raises(ValueError, match="invalid requirement transition"):
        transition_requirement(card, "done")


def test_bug_reopen_threshold_escalates_to_user_decision() -> None:
    bug = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="major",
        status="verifying",
        reopen_count=2,
        owner="qa_agent",
    )
    updated = advance_bug(bug, reopen=True)
    assert updated.status == "needs_user_decision"
    assert updated.reopen_count == 3
```

- [ ] **Step 2: Run flow tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_requirement_flow.py tests/test_bug_flow.py
```

Expected:

- missing flow module imports

- [ ] **Step 3: Implement requirement flow rules**

```python
from __future__ import annotations

from studio.schemas.requirement import RequirementCard, RequirementStatus


_ALLOWED_TRANSITIONS: dict[RequirementStatus, set[RequirementStatus]] = {
    "draft": {"designing"},
    "designing": {"pending_user_review"},
    "pending_user_review": {"approved", "designing"},
    "approved": {"implementing"},
    "implementing": {"self_test_passed"},
    "self_test_passed": {"testing"},
    "testing": {"pending_user_acceptance", "implementing"},
    "pending_user_acceptance": {"quality_check", "implementing"},
    "quality_check": {"done", "implementing"},
    "done": set(),
}


def transition_requirement(card: RequirementCard, next_status: RequirementStatus) -> RequirementCard:
    if next_status not in _ALLOWED_TRANSITIONS[card.status]:
        raise ValueError(f"invalid requirement transition: {card.status} -> {next_status}")
    return card.model_copy(update={"status": next_status})
```

```python
from __future__ import annotations

from studio.schemas.bug import BugCard, BugStatus


_BUG_TRANSITIONS: dict[BugStatus, set[BugStatus]] = {
    "new": {"fixing"},
    "fixing": {"fixed"},
    "fixed": {"verifying"},
    "verifying": {"closed", "reopened", "needs_user_decision"},
    "reopened": {"fixing", "needs_user_decision"},
    "needs_user_decision": {"fixing", "closed"},
    "closed": set(),
}


def transition_bug(card: BugCard, next_status: BugStatus) -> BugCard:
    if next_status not in _BUG_TRANSITIONS[card.status]:
        raise ValueError(f"invalid bug transition: {card.status} -> {next_status}")
    return card.model_copy(update={"status": next_status})


def advance_bug(
    card: BugCard,
    *,
    reopen: bool = False,
    severity_requires_user: bool = False,
    fix_cost_requires_user: bool = False,
    ux_risk_requires_user: bool = False,
) -> BugCard:
    if not reopen:
        return transition_bug(card, "closed")

    reopen_count = card.reopen_count + 1
    needs_user = reopen_count >= 3 or severity_requires_user or fix_cost_requires_user or ux_risk_requires_user
    next_status: BugStatus = "needs_user_decision" if needs_user else "reopened"
    updated = card.model_copy(update={"reopen_count": reopen_count})
    return transition_bug(updated, next_status)
```

- [ ] **Step 4: Run flow tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_requirement_flow.py tests/test_bug_flow.py
```

Expected:

- all flow tests pass

- [ ] **Step 5: Commit**

```batch
git add tests/test_requirement_flow.py tests/test_bug_flow.py studio/domain/requirement_flow.py studio/domain/bug_flow.py
git commit -m "feat: add workflow state machines"
```

## Task 4: Add Approval Services And Audit Logging

**Files:**
- Create: `tests/test_approvals.py`
- Create: `studio/domain/approvals.py`
- Create: `studio/domain/services.py`

- [ ] **Step 1: Write the failing approval tests**

```python
import pytest

from studio.domain.approvals import approve_design_doc, send_back_design_doc
from studio.domain.services import validate_requirement_ready_for_dev
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def test_approving_design_doc_moves_requirement_to_approved() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    updated_doc, updated_requirement, logs = approve_design_doc(requirement, doc, [])
    assert updated_doc.status == "approved"
    assert updated_requirement.status == "approved"
    assert logs[-1].action == "approve"


def test_send_back_design_doc_returns_requirement_to_designing() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    updated_doc, updated_requirement, logs = send_back_design_doc(requirement, doc, "missing edge cases")
    assert updated_doc.status == "sent_back"
    assert updated_requirement.status == "designing"
    assert logs[-1].action == "send_back"


def test_requirement_cannot_enter_implementing_without_approved_design() -> None:
    requirement = RequirementCard(id="req_001", title="Add relic system", status="approved", design_doc_id="design_001")
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    with pytest.raises(ValueError, match="design doc must be approved"):
        validate_requirement_ready_for_dev(requirement, doc, [])
```

- [ ] **Step 2: Run approval tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_approvals.py
```

Expected:

- missing approval and service helpers

- [ ] **Step 3: Implement approval and validation services**

```python
from __future__ import annotations

from datetime import UTC, datetime

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def _log(action: str, target_type: str, target_id: str, message: str) -> ActionLog:
    return ActionLog(
        id=f"log_{int(datetime.now(UTC).timestamp() * 1000)}",
        timestamp=datetime.now(UTC).isoformat(),
        actor="user",
        action=action,
        target_type=target_type,
        target_id=target_id,
        message=message,
        metadata={},
    )


def approve_design_doc(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    balance_tables: list[BalanceTable],
) -> tuple[DesignDoc, RequirementCard, list[ActionLog]]:
    approved_tables = [table for table in balance_tables if table.status == "approved"]
    if balance_tables and len(approved_tables) != len(balance_tables):
        raise ValueError("all balance tables must be approved")
    updated_doc = design_doc.model_copy(update={"status": "approved"})
    updated_requirement = transition_requirement(requirement, "approved")
    return updated_doc, updated_requirement, [_log("approve", "design_doc", design_doc.id, "approved design doc")]


def send_back_design_doc(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    reason: str,
) -> tuple[DesignDoc, RequirementCard, list[ActionLog]]:
    updated_doc = design_doc.model_copy(update={"status": "sent_back"})
    updated_requirement = transition_requirement(requirement, "designing")
    return updated_doc, updated_requirement, [_log("send_back", "design_doc", design_doc.id, reason)]
```

```python
from __future__ import annotations

from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def validate_requirement_ready_for_dev(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    balance_tables: list[BalanceTable],
) -> None:
    if design_doc.status != "approved":
        raise ValueError("design doc must be approved")
    if any(table.status != "approved" for table in balance_tables):
        raise ValueError("balance tables must be approved")
    if requirement.status != "approved":
        raise ValueError("requirement must be approved")
```

- [ ] **Step 4: Run approval tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_approvals.py
```

Expected:

- all approval tests pass

- [ ] **Step 5: Commit**

```batch
git add tests/test_approvals.py studio/domain/approvals.py studio/domain/services.py
git commit -m "feat: add approval services"
```

## Task 5: Add Agent Stubs And Workflow Graph Assembly

**Files:**
- Create: `studio/agents/design.py`
- Create: `studio/agents/dev.py`
- Create: `studio/agents/qa.py`
- Create: `studio/agents/quality.py`
- Create: `studio/agents/art.py`
- Modify: `studio/agents/__init__.py`
- Modify: `studio/runtime/dispatcher.py`
- Modify: `studio/runtime/graph.py`
- Modify: `studio/langgraph_app.py`
- Modify: `tests/test_langgraph_studio.py`

- [ ] **Step 1: Write the failing LangGraph integration test**

```python
from importlib import import_module


def test_langgraph_studio_adapter_exposes_workflow_graphs() -> None:
    module = import_module("studio.langgraph_app")
    assert hasattr(module, "design_graph")
    assert hasattr(module, "delivery_graph")

    result = module.design_graph.invoke({"workspace_root": ".runtime-data/langgraph-dev", "requirement_id": "req_001"})
    assert "requirement_id" in result
    assert result["node_name"] == "design"
```

- [ ] **Step 2: Run the targeted LangGraph test to verify failure**

Run:

```batch
uv run pytest -q tests/test_langgraph_studio.py
```

Expected:

- missing graph exports or failing assertions

- [ ] **Step 3: Implement minimal agent stubs and runtime dispatcher**

```python
from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DesignAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"telemetry": {"node": "design"}},
            trace={"node": "design", "result": "drafted_design"},
        )
```

```python
from __future__ import annotations

from studio.agents.art import ArtAgent
from studio.agents.design import DesignAgent
from studio.agents.dev import DevAgent
from studio.agents.qa import QaAgent
from studio.agents.quality import QualityAgent


class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agents = {
            "design": DesignAgent(),
            "dev": DevAgent(),
            "qa": QaAgent(),
            "quality": QualityAgent(),
            "art": ArtAgent(),
        }

    def get(self, node_name: str):
        return self._agents[node_name]
```

```python
from __future__ import annotations

from langgraph.graph import END, START, StateGraph


def build_design_graph():
    graph = StateGraph(dict)

    def design_node(state: dict[str, object]) -> dict[str, object]:
        return {**state, "node_name": "design"}

    graph.add_node("design", design_node)
    graph.add_edge(START, "design")
    graph.add_edge("design", END)
    return graph.compile()


def build_delivery_graph():
    graph = StateGraph(dict)

    def dev_node(state: dict[str, object]) -> dict[str, object]:
        return {**state, "node_name": "dev"}

    def qa_node(state: dict[str, object]) -> dict[str, object]:
        return {**state, "node_name": "qa"}

    def quality_node(state: dict[str, object]) -> dict[str, object]:
        return {**state, "node_name": "quality"}

    graph.add_node("dev", dev_node)
    graph.add_node("qa", qa_node)
    graph.add_node("quality", quality_node)
    graph.add_edge(START, "dev")
    graph.add_edge("dev", "qa")
    graph.add_edge("qa", "quality")
    graph.add_edge("quality", END)
    return graph.compile()
```

```python
from studio.runtime.graph import build_delivery_graph, build_design_graph

design_graph = build_design_graph()
delivery_graph = build_delivery_graph()
graph = design_graph
```

- [ ] **Step 4: Run the targeted LangGraph test to verify it passes**

Run:

```batch
uv run pytest -q tests/test_langgraph_studio.py
```

Expected:

- the Studio module exports the new graphs and the test passes

- [ ] **Step 5: Commit**

```batch
git add studio/agents/design.py studio/agents/dev.py studio/agents/qa.py studio/agents/quality.py studio/agents/art.py studio/agents/__init__.py studio/runtime/dispatcher.py studio/runtime/graph.py studio/langgraph_app.py tests/test_langgraph_studio.py
git commit -m "feat: add workflow graph scaffolding"
```

## Task 6: Add Command-Style CLI For Requirements, Design, And Workflow Execution

**Files:**
- Create: `tests/test_workflow_cli.py`
- Modify: `studio/interfaces/cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app


def test_requirement_create_and_list(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        [
            "requirement",
            "create",
            "--workspace",
            str(tmp_path),
            "--title",
            "Add relic system",
        ],
    )
    assert create_result.exit_code == 0
    assert "req_" in create_result.stdout

    list_result = runner.invoke(app, ["requirement", "list", "--workspace", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "Add relic system" in list_result.stdout


def test_workflow_run_design_creates_design_doc(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]

    result = runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    assert result.exit_code == 0
    assert "design_" in result.stdout


def test_design_approve_moves_requirement_to_approved(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    result = runner.invoke(app, ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", "req_001"])
    assert result.exit_code == 0
    assert "approved" in result.stdout


def test_workflow_run_dev_and_qa_generates_bug_on_failure(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    runner.invoke(app, ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    runner.invoke(app, ["workflow", "run-dev", "--workspace", str(tmp_path), "--requirement-id", requirement_id])

    result = runner.invoke(
        app,
        ["workflow", "run-qa", "--workspace", str(tmp_path), "--requirement-id", requirement_id, "--fail"],
    )
    assert result.exit_code == 0
    assert "bug_" in result.stdout
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_workflow_cli.py
```

Expected:

- command lookup failures or missing behavior assertions

- [ ] **Step 3: Implement minimal command groups and handlers**

```python
from pathlib import Path

import typer

from studio.domain.approvals import approve_design_doc
from studio.domain.requirement_flow import transition_requirement
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace

app = typer.Typer()
requirement_app = typer.Typer()
design_app = typer.Typer()
workflow_app = typer.Typer()

app.add_typer(requirement_app, name="requirement")
app.add_typer(design_app, name="design")
app.add_typer(workflow_app, name="workflow")


@requirement_app.command("create")
def create_requirement(workspace: str, title: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    store.ensure_layout()
    object_id = f"req_{len(store.requirements.list_all()) + 1:03d}"
    card = RequirementCard(id=object_id, title=title)
    store.requirements.save(card)
    typer.echo(f"{card.id} {card.title} {card.status}")


@requirement_app.command("list")
def list_requirements(workspace: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    for card in store.requirements.list_all():
        typer.echo(f"{card.id} {card.priority} {card.status} {card.title}")
```

```python
@workflow_app.command("run-design")
def run_design(workspace: str, requirement_id: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(requirement_id)
    designing = transition_requirement(requirement, "designing")
    pending = transition_requirement(designing, "pending_user_review")
    design_doc = DesignDoc(
        id=f"design_{requirement_id.split('_')[-1]}",
        requirement_id=requirement.id,
        title=f"{requirement.title} Design",
        summary=requirement.title,
        core_rules=["rule 1"],
        acceptance_criteria=["criterion 1"],
        open_questions=["question 1"],
        status="pending_user_review",
    )
    updated_requirement = pending.model_copy(update={"design_doc_id": design_doc.id})
    store.design_docs.save(design_doc)
    store.requirements.save(updated_requirement)
    typer.echo(f"{design_doc.id} pending_user_review")
```

```python
@design_app.command("approve")
def approve_design(workspace: str, requirement_id: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(requirement_id)
    design_doc = store.design_docs.get(requirement.design_doc_id or "")
    updated_doc, updated_requirement, logs = approve_design_doc(requirement, design_doc, [])
    store.design_docs.save(updated_doc)
    store.requirements.save(updated_requirement)
    for log in logs:
        store.logs.save(log)
    typer.echo(f"{updated_doc.id} {updated_doc.status} {updated_requirement.status}")
```

```python
@workflow_app.command("run-dev")
def run_dev(workspace: str, requirement_id: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(requirement_id)
    updated_requirement = transition_requirement(requirement, "implementing")
    tested_requirement = transition_requirement(updated_requirement, "self_test_passed")
    store.requirements.save(tested_requirement)
    typer.echo(f"{tested_requirement.id} {tested_requirement.status}")


@workflow_app.command("run-qa")
def run_qa(workspace: str, requirement_id: str, fail: bool = False) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(requirement_id)
    testing_requirement = transition_requirement(requirement, "testing")
    if not fail:
        accepted_requirement = transition_requirement(testing_requirement, "pending_user_acceptance")
        store.requirements.save(accepted_requirement)
        typer.echo(f"{accepted_requirement.id} {accepted_requirement.status}")
        return

    implementing_requirement = transition_requirement(testing_requirement, "implementing")
    bug_id = f"bug_{len(store.bugs.list_all()) + 1:03d}"
    bug = BugCard(
        id=bug_id,
        requirement_id=requirement_id,
        title=f"QA failure for {requirement_id}",
        severity="major",
        status="new",
        owner="qa_agent",
        repro_steps=["generated by qa"],
        notes=[],
    )
    updated_requirement = implementing_requirement.model_copy(
        update={"bug_ids": [*implementing_requirement.bug_ids, bug.id]}
    )
    store.bugs.save(bug)
    store.requirements.save(updated_requirement)
    typer.echo(f"{bug.id} {updated_requirement.status}")


@workflow_app.command("run-quality")
def run_quality(workspace: str, requirement_id: str) -> None:
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    requirement = store.requirements.get(requirement_id)
    checking_requirement = transition_requirement(requirement, "quality_check")
    done_requirement = transition_requirement(checking_requirement, "done")
    store.requirements.save(done_requirement)
    typer.echo(f"{done_requirement.id} {done_requirement.status}")
```

- [ ] **Step 4: Run CLI tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_workflow_cli.py
```

Expected:

- all CLI workflow tests pass

- [ ] **Step 5: Commit**

```batch
git add tests/test_workflow_cli.py studio/interfaces/cli.py
git commit -m "feat: add workflow cli commands"
```

## Task 7: Replace Demo Graph Behavior With Repository-Backed Workflow Execution

**Files:**
- Modify: `studio/runtime/graph.py`
- Modify: `tests/test_graph_run.py`

- [ ] **Step 1: Write the failing graph test for repository-backed execution**

```python
from pathlib import Path

from studio.runtime.graph import build_design_graph


def test_design_graph_updates_requirement_and_design_doc(tmp_path: Path) -> None:
    runtime = build_design_graph()
    result = runtime.invoke({"workspace_root": str(tmp_path / ".studio-data"), "requirement_id": "req_001"})

    assert result["requirement_id"] == "req_001"
    assert result["node_name"] == "design"
    assert "design_doc_id" in result
```

- [ ] **Step 2: Run targeted graph tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_graph_run.py tests/test_langgraph_studio.py
```

Expected:

- failing assertions until graph writes through repositories

- [ ] **Step 3: Implement repository-backed graph nodes**

```python
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.design_doc import DesignDoc
from studio.storage.workspace import StudioWorkspace


def build_design_graph():
    graph = StateGraph(dict)

    def design_node(state: dict[str, object]) -> dict[str, object]:
        workspace = StudioWorkspace(Path(str(state["workspace_root"])))
        requirement = workspace.requirements.get(str(state["requirement_id"]))
        designing = transition_requirement(requirement, "designing")
        pending = transition_requirement(designing, "pending_user_review")
        design_doc = DesignDoc(
            id=f"design_{requirement.id.split('_')[-1]}",
            requirement_id=requirement.id,
            title=f"{requirement.title} Design",
            summary=requirement.title,
            core_rules=["rule 1"],
            acceptance_criteria=["criterion 1"],
            open_questions=["question 1"],
            status="pending_user_review",
        )
        workspace.design_docs.save(design_doc)
        workspace.requirements.save(pending.model_copy(update={"design_doc_id": design_doc.id}))
        return {
            **state,
            "node_name": "design",
            "requirement_id": requirement.id,
            "design_doc_id": design_doc.id,
        }

    graph.add_node("design", design_node)
    graph.add_edge(START, "design")
    graph.add_edge("design", END)
    return graph.compile()
```

- [ ] **Step 4: Run targeted graph tests to verify they pass**

Run:

```batch
uv run pytest -q tests/test_graph_run.py tests/test_langgraph_studio.py
```

Expected:

- updated graph tests pass with repository-backed state changes

- [ ] **Step 5: Commit**

```batch
git add studio/runtime/graph.py tests/test_graph_run.py tests/test_langgraph_studio.py
git commit -m "feat: back workflow graphs with repositories"
```

## Task 8: Add Full Regression Coverage And Refresh Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the new CLI workflow**

~~~markdown
## Workflow CLI

Create a requirement:

```batch
uv run python -m studio.interfaces.cli requirement create --workspace .runtime-data --title "Add relic system"
```

Run design generation:

```batch
uv run python -m studio.interfaces.cli workflow run-design --workspace .runtime-data --requirement-id req_001
```

Approve the design:

```batch
uv run python -m studio.interfaces.cli design approve --workspace .runtime-data --requirement-id req_001
```

Inspect graphs in LangGraph Studio:

```batch
langgraph dev
```
~~~

- [ ] **Step 2: Run focused regression tests**

Run:

```batch
uv run pytest -q tests/test_workflow_schemas.py tests/test_workflow_repositories.py tests/test_requirement_flow.py tests/test_bug_flow.py tests/test_approvals.py tests/test_workflow_cli.py tests/test_graph_run.py tests/test_langgraph_studio.py
```

Expected:

- all new workflow tests pass

- [ ] **Step 3: Run the full test suite**

Run:

```batch
uv run pytest -q
```

Expected:

- full suite passes

- [ ] **Step 4: Commit**

```batch
git add README.md
git commit -m "docs: document workflow collaboration kernel"
```

## Self-Review Checklist

- [ ] The plan covers all phase 1 backend goals from the approved spec.
- [ ] No task depends on hidden behavior not introduced earlier in the plan.
- [ ] CLI remains the primary interaction surface.
- [ ] `langgraph dev` stays supported through exported graphs.
- [ ] Requirement approval gates are enforced outside agents.
- [ ] Bug escalation rules are covered in both code and tests.
- [ ] Storage remains local JSON and does not introduce a database dependency.
