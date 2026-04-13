# LangGraph Game Studio Runtime Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working version of a LangGraph-based game-studio runtime kernel that can execute a small multi-agent workflow, store structured state and artifacts, recover from failure checkpoints, and support human approval gates.

**Architecture:** Use Python with LangGraph for explicit graph orchestration, Pydantic for schemas, Typer for the CLI, and pytest for contract and recovery tests. Keep the runtime core separate from agent adapters, artifact persistence, and memory services so new game-domain agents can be added without changing the orchestration engine.

**Tech Stack:** Python 3.12, LangGraph, LangChain core messages, Pydantic v2, Typer, pytest, pytest-mock

---

## Planned File Structure

Create these files during implementation:

- `pyproject.toml` - Python project metadata, dependencies, and pytest config
- `README.md` - project setup and quickstart
- `studio/schemas/runtime.py` - runtime state, node result, decisions, human gate schemas
- `studio/schemas/artifact.py` - artifact and artifact lineage schemas
- `studio/artifacts/registry.py` - artifact registry implementation backed by JSON files
- `studio/memory/store.py` - structured run/project/artifact/pattern memory store
- `studio/runtime/checkpoints.py` - checkpoint save/load primitives
- `studio/runtime/policy.py` - retry, escalate, and recovery policy mapping
- `studio/runtime/dispatcher.py` - node dispatch logic
- `studio/runtime/graph.py` - LangGraph assembly using planner, worker, reviewer nodes
- `studio/agents/base.py` - agent protocol and shared adapter types
- `studio/agents/planner.py` - planner node adapter
- `studio/agents/worker.py` - worker node adapter
- `studio/agents/reviewer.py` - reviewer node adapter
- `studio/interfaces/cli.py` - CLI entrypoint for running a demo workflow
- `tests/test_schemas.py` - schema validation tests
- `tests/test_artifact_registry.py` - artifact versioning and lineage tests
- `tests/test_memory_store.py` - structured memory tests
- `tests/test_recovery_policy.py` - retry, escalation, and checkpoint policy tests
- `tests/test_graph_run.py` - end-to-end runtime graph tests

Modify these files during implementation:

- `docs/superpowers/specs/2026-04-10-langgraph-game-studio-runtime-kernel-design.md` - add implementation status link once core runtime lands
- `docs/superpowers/plans/2026-04-10-langgraph-game-studio-runtime-kernel.md` - check off completed steps while executing

### Task 1: Bootstrap The Python Runtime Project

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `studio/__init__.py`
- Create: `studio/runtime/__init__.py`
- Create: `studio/agents/__init__.py`
- Create: `studio/artifacts/__init__.py`
- Create: `studio/memory/__init__.py`
- Create: `studio/interfaces/__init__.py`
- Create: `studio/schemas/__init__.py`
- Test: `python -m pytest`

- [x] **Step 1: Write the failing bootstrap smoke test**

```python
# tests/test_bootstrap.py
from importlib import import_module


def test_cli_module_imports() -> None:
    module = import_module("studio.interfaces.cli")
    assert hasattr(module, "app")
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.interfaces.cli'`

- [x] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "game-studio-runtime"
version = "0.1.0"
description = "LangGraph-based multi-agent runtime kernel for game production workflows."
requires-python = ">=3.12"
dependencies = [
  "langgraph",
  "langchain-core",
  "pydantic>=2.7",
  "typer>=0.12",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-mock>=3.14",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```python
# studio/interfaces/cli.py
import typer

app = typer.Typer(help="Game Studio Runtime Kernel CLI.")
```

```markdown
# README.md

## Game Studio Runtime Kernel

Initial LangGraph runtime kernel for orchestrating multi-agent game production workflows.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -v
```
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add pyproject.toml README.md studio tests/test_bootstrap.py
git commit -m "chore: bootstrap python runtime project"
```

### Task 2: Define Core Schemas For Runtime State And Node Results

**Files:**
- Create: `studio/schemas/runtime.py`
- Create: `studio/schemas/artifact.py`
- Test: `tests/test_schemas.py`

- [x] **Step 1: Write the failing schema tests**

```python
# tests/test_schemas.py
from studio.schemas.artifact import ArtifactRecord
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


def test_runtime_state_defaults() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a simple 2D game concept"},
    )
    assert state.plan.current_node is None
    assert state.artifacts == []
    assert state.risks == []


def test_node_result_requires_known_decision() -> None:
    result = NodeResult(
        decision=NodeDecision.CONTINUE,
        state_patch={"risks": ["none"]},
        artifacts=[],
        trace={"node": "planner"},
    )
    assert result.decision is NodeDecision.CONTINUE


def test_artifact_record_tracks_lineage() -> None:
    artifact = ArtifactRecord(
        artifact_id="artifact-001",
        artifact_type="design_brief",
        version=2,
        source_node="reviewer",
        parent_artifact_id="artifact-000",
        review_status="approved",
        tags=["concept"],
        payload={"title": "Sky Forge"},
    )
    assert artifact.parent_artifact_id == "artifact-000"
    assert artifact.version == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: FAIL with import errors for `studio.schemas.runtime` and `studio.schemas.artifact`

- [x] **Step 3: Write minimal implementation**

```python
# studio/schemas/artifact.py
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
```

```python
# studio/schemas/runtime.py
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add studio/schemas tests/test_schemas.py
git commit -m "feat: add runtime and artifact schemas"
```

### Task 3: Implement Artifact Registry With Versioning And Lineage

**Files:**
- Create: `studio/artifacts/registry.py`
- Test: `tests/test_artifact_registry.py`

- [x] **Step 1: Write the failing artifact registry test**

```python
# tests/test_artifact_registry.py
from pathlib import Path

from studio.artifacts.registry import ArtifactRegistry
from studio.schemas.artifact import ArtifactRecord


def test_registry_versions_artifacts_by_parent(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    first = ArtifactRecord(
        artifact_id="concept-001",
        artifact_type="design_brief",
        source_node="worker",
        payload={"title": "Dungeon Bloom"},
    )
    second = ArtifactRecord(
        artifact_id="concept-002",
        artifact_type="design_brief",
        source_node="reviewer",
        parent_artifact_id="concept-001",
        payload={"title": "Dungeon Bloom Revised"},
    )

    stored_first = registry.save(first)
    stored_second = registry.save(second)

    assert stored_first.version == 1
    assert stored_second.version == 2
    assert registry.load("concept-002").parent_artifact_id == "concept-001"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_artifact_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.artifacts.registry'`

- [x] **Step 3: Write minimal implementation**

```python
# studio/artifacts/registry.py
from __future__ import annotations

import json
from pathlib import Path

from studio.schemas.artifact import ArtifactRecord


class ArtifactRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, artifact: ArtifactRecord) -> ArtifactRecord:
        version = 1
        if artifact.parent_artifact_id is not None:
            parent = self.load(artifact.parent_artifact_id)
            version = parent.version + 1

        stored = artifact.model_copy(update={"version": version})
        target = self.root / f"{stored.artifact_id}.json"
        target.write_text(stored.model_dump_json(indent=2), encoding="utf-8")
        return stored

    def load(self, artifact_id: str) -> ArtifactRecord:
        target = self.root / f"{artifact_id}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        return ArtifactRecord.model_validate(payload)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_artifact_registry.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add studio/artifacts/registry.py tests/test_artifact_registry.py
git commit -m "feat: add artifact registry with lineage"
```

### Task 4: Implement Structured Memory Store

**Files:**
- Create: `studio/memory/store.py`
- Test: `tests/test_memory_store.py`

- [x] **Step 1: Write the failing memory store test**

```python
# tests/test_memory_store.py
from pathlib import Path

from studio.memory.store import MemoryStore


def test_memory_store_saves_project_and_run_entries(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.put("project", "world-rules", {"tone": "hopeful", "camera": "top-down"})
    store.put("run", "run-001-summary", {"summary": "planner selected the demo graph"})

    assert store.get("project", "world-rules")["tone"] == "hopeful"
    assert store.get("run", "run-001-summary")["summary"] == "planner selected the demo graph"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.memory.store'`

- [x] **Step 3: Write minimal implementation**

```python
# studio/memory/store.py
from __future__ import annotations

import json
from pathlib import Path


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, bucket: str, key: str, value: dict[str, object]) -> None:
        bucket_dir = self.root / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        (bucket_dir / f"{key}.json").write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )

    def get(self, bucket: str, key: str) -> dict[str, object]:
        target = self.root / bucket / f"{key}.json"
        return json.loads(target.read_text(encoding="utf-8"))
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory_store.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add studio/memory/store.py tests/test_memory_store.py
git commit -m "feat: add structured memory store"
```

### Task 5: Implement Checkpoints And Recovery Policy

**Files:**
- Create: `studio/runtime/checkpoints.py`
- Create: `studio/runtime/policy.py`
- Test: `tests/test_recovery_policy.py`

- [ ] **Step 1: Write the failing recovery tests**

```python
# tests/test_recovery_policy.py
from pathlib import Path

from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.policy import RecoveryAction, RecoveryPolicy
from studio.schemas.runtime import RuntimeState


def test_checkpoint_manager_round_trips_runtime_state(tmp_path: Path) -> None:
    manager = CheckpointManager(tmp_path / "checkpoints")
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a game"},
    )
    manager.save("planner", state)
    restored = manager.load("planner")
    assert restored.run_id == "run-001"


def test_recovery_policy_maps_error_types_to_actions() -> None:
    policy = RecoveryPolicy(max_retries=1)
    assert policy.resolve("tool_failure", attempt=0) is RecoveryAction.RETRY
    assert policy.resolve("quality_gate_failure", attempt=1) is RecoveryAction.ESCALATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recovery_policy.py -v`
Expected: FAIL with import errors for checkpoint and policy modules

- [ ] **Step 3: Write minimal implementation**

```python
# studio/runtime/checkpoints.py
from __future__ import annotations

import json
from pathlib import Path

from studio.schemas.runtime import RuntimeState


class CheckpointManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, node_name: str, state: RuntimeState) -> None:
        target = self.root / f"{node_name}.json"
        target.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def load(self, node_name: str) -> RuntimeState:
        payload = json.loads((self.root / f"{node_name}.json").read_text(encoding="utf-8"))
        return RuntimeState.model_validate(payload)
```

```python
# studio/runtime/policy.py
from __future__ import annotations

from enum import StrEnum


class RecoveryAction(StrEnum):
    RETRY = "retry"
    ESCALATE = "escalate"
    RESUME = "resume"
    STOP = "stop"


class RecoveryPolicy:
    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries

    def resolve(self, error_type: str, attempt: int) -> RecoveryAction:
        if error_type == "tool_failure" and attempt < self.max_retries:
            return RecoveryAction.RETRY
        if error_type in {"quality_gate_failure", "state_conflict"}:
            return RecoveryAction.ESCALATE
        if error_type == "missing_dependency":
            return RecoveryAction.STOP
        return RecoveryAction.RESUME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recovery_policy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/runtime/checkpoints.py studio/runtime/policy.py tests/test_recovery_policy.py
git commit -m "feat: add checkpoint and recovery policy"
```

### Task 6: Add Agent Protocol And Demo Agent Adapters

**Files:**
- Create: `studio/agents/base.py`
- Create: `studio/agents/planner.py`
- Create: `studio/agents/worker.py`
- Create: `studio/agents/reviewer.py`
- Test: `tests/test_agent_adapters.py`

- [ ] **Step 1: Write the failing agent adapter tests**

```python
# tests/test_agent_adapters.py
from studio.agents.planner import PlannerAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent
from studio.schemas.runtime import NodeDecision, RuntimeState


def test_planner_agent_sets_first_pending_nodes() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = PlannerAgent().run(state)
    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["pending_nodes"] == ["worker", "reviewer"]


def test_reviewer_agent_requests_retry_for_missing_title() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = ReviewerAgent().run(state, artifact_payload={"summary": "missing title"})
    assert result.decision is NodeDecision.RETRY


def test_worker_agent_produces_design_artifact() -> None:
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a 2D farming game"},
    )
    result = WorkerAgent().run(state)
    assert result.artifacts[0].artifact_type == "design_brief"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent_adapters.py -v`
Expected: FAIL with import errors for planner, worker, and reviewer agents

- [ ] **Step 3: Write minimal implementation**

```python
# studio/agents/base.py
from __future__ import annotations

from typing import Protocol

from studio.schemas.runtime import NodeResult, RuntimeState


class RuntimeAgent(Protocol):
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        ...
```

```python
# studio/agents/planner.py
from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class PlannerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "plan": {
                    "graph_name": "game_studio_demo",
                    "current_node": "planner",
                    "pending_nodes": ["worker", "reviewer"],
                    "completed_nodes": [],
                }
            },
            trace={"node": "planner", "reason": "initialized demo graph"},
        )
```

```python
# studio/agents/worker.py
from __future__ import annotations

from studio.schemas.artifact import ArtifactRecord
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class WorkerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        artifact = ArtifactRecord(
            artifact_id="concept-draft",
            artifact_type="design_brief",
            source_node="worker",
            payload={
                "title": "Moonwell Garden",
                "summary": state.goal["prompt"],
                "genre": "2d cozy strategy",
            },
        )
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"plan": {"current_node": "worker"}},
            artifacts=[artifact],
            trace={"node": "worker"},
        )
```

```python
# studio/agents/reviewer.py
from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ReviewerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        artifact_payload = kwargs.get("artifact_payload", {})
        decision = NodeDecision.CONTINUE if "title" in artifact_payload else NodeDecision.RETRY
        return NodeResult(
            decision=decision,
            state_patch={"plan": {"current_node": "reviewer"}},
            trace={"node": "reviewer", "decision": decision.value},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agent_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/agents tests/test_agent_adapters.py
git commit -m "feat: add demo planner worker reviewer agents"
```

### Task 7: Build Dispatcher And LangGraph Runtime Assembly

**Files:**
- Create: `studio/runtime/dispatcher.py`
- Create: `studio/runtime/graph.py`
- Test: `tests/test_graph_run.py`

- [ ] **Step 1: Write the failing runtime graph tests**

```python
# tests/test_graph_run.py
from pathlib import Path

from studio.runtime.graph import build_demo_runtime


def test_demo_runtime_runs_to_completion(tmp_path: Path) -> None:
    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert result["plan"]["current_node"] == "reviewer"
    assert result["artifacts"][0]["artifact_type"] == "design_brief"
    assert result["telemetry"]["status"] == "completed"


def test_demo_runtime_surfaces_retry_when_review_fails(tmp_path: Path) -> None:
    runtime = build_demo_runtime(tmp_path, force_review_retry=True)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert "review retry requested" in result["risks"]
    assert result["telemetry"]["status"] == "needs_attention"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graph_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.runtime.graph'`

- [ ] **Step 3: Write minimal implementation**

```python
# studio/runtime/dispatcher.py
from __future__ import annotations

from studio.agents.planner import PlannerAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent


class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agents = {
            "planner": PlannerAgent(),
            "worker": WorkerAgent(),
            "reviewer": ReviewerAgent(),
        }

    def get(self, node_name: str):
        return self._agents[node_name]
```

```python
# studio/runtime/graph.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from studio.artifacts.registry import ArtifactRegistry
from studio.memory.store import MemoryStore
from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.dispatcher import RuntimeDispatcher
from studio.schemas.runtime import RuntimeState


def build_demo_runtime(root: Path, force_review_retry: bool = False):
    dispatcher = RuntimeDispatcher()
    artifact_registry = ArtifactRegistry(root / "artifacts")
    memory_store = MemoryStore(root / "memory")
    checkpoints = CheckpointManager(root / "checkpoints")

    def planner_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState(
            project_id="demo-project",
            run_id="run-001",
            task_id="task-001",
            goal=state,
        )
        result = dispatcher.get("planner").run(runtime_state)
        checkpoints.save("planner", runtime_state)
        return runtime_state.model_copy(update=result.state_patch).model_dump(mode="json")

    def worker_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        result = dispatcher.get("worker").run(runtime_state)
        stored = [artifact_registry.save(artifact) for artifact in result.artifacts]
        memory_store.put("run", "run-001-summary", {"summary": "worker produced concept draft"})
        updated = runtime_state.model_copy(
            update={
                "artifacts": stored,
                "plan": {**runtime_state.plan.model_dump(), **result.state_patch["plan"]},
            }
        )
        checkpoints.save("worker", updated)
        return updated.model_dump(mode="json")

    def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
        runtime_state = RuntimeState.model_validate(state)
        payload = {} if force_review_retry else runtime_state.artifacts[0].payload
        result = dispatcher.get("reviewer").run(runtime_state, artifact_payload=payload)
        risks = ["review retry requested"] if result.decision.value == "retry" else []
        status = "needs_attention" if risks else "completed"
        updated = runtime_state.model_copy(
            update={
                "risks": risks,
                "telemetry": {"status": status},
                "plan": {**runtime_state.plan.model_dump(), **result.state_patch["plan"]},
            }
        )
        checkpoints.save("reviewer", updated)
        return updated.model_dump(mode="json")

    graph = StateGraph(dict)
    graph.add_node("planner", planner_node)
    graph.add_node("worker", worker_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graph_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/runtime/dispatcher.py studio/runtime/graph.py tests/test_graph_run.py
git commit -m "feat: add demo langgraph runtime flow"
```

### Task 8: Add CLI Execution, Human Gate Demo, And Final Verification

**Files:**
- Modify: `studio/interfaces/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
# tests/test_cli.py
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app


def test_run_demo_command_outputs_completion_status(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-demo",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Design a simple 2D game concept",
        ],
    )

    assert result.exit_code == 0
    assert '"status": "completed"' in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `No such command 'run-demo'`

- [ ] **Step 3: Write minimal implementation**

```python
# studio/interfaces/cli.py
from __future__ import annotations

import json
from pathlib import Path

import typer

from studio.runtime.graph import build_demo_runtime

app = typer.Typer(help="Game Studio Runtime Kernel CLI.")


@app.command("run-demo")
def run_demo(workspace: Path, prompt: str, require_approval: bool = False) -> None:
    runtime = build_demo_runtime(workspace)
    result = runtime.invoke({"prompt": prompt})
    if require_approval:
        result["human_gates"] = [{"gate_id": "approval-001", "reason": "final approval", "status": "pending"}]
        result["telemetry"]["status"] = "awaiting_approval"
    typer.echo(json.dumps(result, indent=2))
```

```markdown
# README.md

## Game Studio Runtime Kernel

Initial LangGraph runtime kernel for orchestrating multi-agent game production workflows.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -v
```

## Demo

```bash
python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run final verification suite**

Run: `python -m pytest -v`
Expected: PASS for bootstrap, schema, artifact, memory, recovery, agent, graph, and CLI tests

- [ ] **Step 6: Commit**

```bash
git add studio/interfaces/cli.py README.md tests/test_cli.py
git commit -m "feat: add cli runtime demo and verification"
```

## Self-Review

### Spec Coverage

- Layered architecture: covered by Tasks 1, 6, 7, and 8
- Structured runtime state: covered by Task 2
- Planner / Worker / Reviewer node types: covered by Task 6
- Artifact registry and lineage: covered by Task 3
- Structured memory: covered by Task 4
- Recovery and checkpoints: covered by Task 5
- Explicit LangGraph runtime flow: covered by Task 7
- CLI / thin interface layer: covered by Task 8
- Validation demos: covered by Tasks 7 and 8

No spec gaps found for the first implementation slice.

### Placeholder Scan

- No `TBD`, `TODO`, or deferred implementation placeholders remain.
- Each task includes exact file paths, code snippets, commands, and expected outcomes.

### Type Consistency

- Runtime schemas consistently use `RuntimeState`, `NodeResult`, `NodeDecision`, and `ArtifactRecord`.
- Runtime flow uses the same node names across planner, worker, reviewer, dispatcher, and tests.
- Recovery policy uses explicit error type strings that match the recovery tests.
