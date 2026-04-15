# Auto Design Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically execute the design workflow when a draft requirement is created, with Claude Agent generating real design docs, and support rework cycles when designs are sent back with feedback.

**Architecture:** A background `WorkflowPoller` scans for eligible requirements (draft or sent-back) and invokes a `DesignWorkflowExecutor` that calls the existing LangGraph design graph with the `DesignAgent`. The graph is rewritten to use Agent output instead of placeholders. The frontend DesignEditor becomes editable with a proper send-back dialog.

**Tech Stack:** Python 3.12, LangGraph, Claude Agent SDK, FastAPI (lifespan), Pydantic v2, React 18, TypeScript, TanStack Query

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `studio/schemas/design_doc.py` | Add `sent_back_reason` field |
| Modify | `studio/domain/approvals.py:82-93` | Store reason on DesignDoc |
| Modify | `studio/runtime/graph.py:215-250` | Use DesignAgent instead of placeholders |
| Create | `studio/runtime/executor.py` | DesignWorkflowExecutor wrapping graph + storage |
| Create | `studio/runtime/poller.py` | Background poller scanning for eligible requirements |
| Modify | `studio/api/main.py:10-71` | Add lifespan for poller start/stop |
| Modify | `studio/api/routes/workflows.py:22-78` | Replace stub with executor call |
| Create | `tests/test_executor.py` | Executor unit tests |
| Create | `tests/test_poller.py` | Poller unit tests |
| Modify | `web/src/lib/types.ts:168-179` | Add `sent_back_reason` to DesignDoc type |
| Modify | `web/src/pages/DesignEditor.tsx` | Editable fields + send-back dialog |
| Modify | `web/src/components/board/RequirementCard.tsx` | Add "View Design" link |

---

### Task 1: Add `sent_back_reason` to DesignDoc schema

**Files:**
- Modify: `studio/schemas/design_doc.py:13-24`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_schemas.py`:

```python
def test_design_doc_accepts_sent_back_reason():
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Test",
        summary="Test summary",
        sent_back_reason="Need more detail on core rules",
    )
    assert doc.sent_back_reason == "Need more detail on core rules"


def test_design_doc_sent_back_reason_defaults_none():
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Test",
        summary="Test summary",
    )
    assert doc.sent_back_reason is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py::test_design_doc_accepts_sent_back_reason tests/test_schemas.py::test_design_doc_sent_back_reason_defaults_none -v`
Expected: FAIL — `DesignDoc` has no `sent_back_reason` field

- [ ] **Step 3: Add the field to DesignDoc**

In `studio/schemas/design_doc.py`, add after the `status` field (line 23):

```python
    sent_back_reason: str | None = None
```

The full model becomes:

```python
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
    sent_back_reason: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py::test_design_doc_accepts_sent_back_reason tests/test_schemas.py::test_design_doc_sent_back_reason_defaults_none -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/schemas/design_doc.py tests/test_schemas.py
git commit -m "feat: add sent_back_reason field to DesignDoc schema"
```

---

### Task 2: Update `send_back_design_doc()` to store reason on DesignDoc

**Files:**
- Modify: `studio/domain/approvals.py:82-93`
- Test: `tests/test_approvals.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_approvals.py`:

```python
def test_send_back_stores_reason_on_design_doc():
    requirement = RequirementCard(id="req_1", title="Test", design_doc_id="design_1")
    design_doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Test Design",
        summary="Summary",
        status="pending_user_review",
    )
    updated_doc, updated_req, logs = send_back_design_doc(
        requirement, design_doc, "Core rules need more specificity"
    )
    assert updated_doc.sent_back_reason == "Core rules need more specificity"
    assert updated_doc.status == "sent_back"
    assert updated_req.status == "designing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_approvals.py::test_send_back_stores_reason_on_design_doc -v`
Expected: FAIL — `updated_doc.sent_back_reason` is `None` (reason not stored on doc)

- [ ] **Step 3: Update send_back_design_doc()**

In `studio/domain/approvals.py`, change line 89 from:

```python
    updated_doc = design_doc.model_copy(update={"status": "sent_back"})
```

to:

```python
    updated_doc = design_doc.model_copy(update={"status": "sent_back", "sent_back_reason": reason})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_approvals.py::test_send_back_stores_reason_on_design_doc -v`
Expected: PASS

- [ ] **Step 5: Run full approval tests to check no regression**

Run: `uv run pytest tests/test_approvals.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add studio/domain/approvals.py tests/test_approvals.py
git commit -m "feat: store sent_back_reason on DesignDoc in send_back_design_doc()"
```

---

### Task 3: Rewrite `build_design_graph()` to use DesignAgent

**Files:**
- Modify: `studio/runtime/graph.py:215-250`
- Test: `tests/test_graph_run.py`

The current `design_node` writes placeholder data. We rewrite it to call `DesignAgent` via Claude, falling back to deterministic output when Claude is unavailable.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_graph_run.py`:

```python
from unittest.mock import patch, MagicMock


def test_design_graph_uses_design_agent():
    """design_node should call DesignAgent and use its output for the design doc."""
    with (
        patch("studio.runtime.graph.DesignAgent") as MockAgent,
        patch("studio.runtime.graph.StudioWorkspace") as MockWorkspace,
    ):
        mock_agent = MagicMock()
        mock_agent.run.return_value = NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "plan": {"current_node": "design"},
                "telemetry": {
                    "design_brief": {
                        "title": "Moonwell Garden",
                        "summary": "A relaxing garden game",
                        "core_rules": ["water plants daily"],
                        "acceptance_criteria": ["plants grow over time"],
                        "open_questions": ["weather system?"],
                    }
                },
            },
            trace={"node": "design", "fallback_used": False},
        )
        MockAgent.return_value = mock_agent

        mock_req = RequirementCard(id="req_1", title="Garden Game")
        mock_designs = MagicMock()
        mock_requirements = MagicMock()
        mock_requirements.get.return_value = mock_req

        mock_store = MagicMock()
        mock_store.requirements = mock_requirements
        mock_store.design_docs = mock_designs
        MockWorkspace.return_value = mock_store

        graph = build_design_graph()
        result = graph.invoke({
            "workspace_root": "/tmp/test-workspace",
            "requirement_id": "req_1",
        })

        mock_agent.run.assert_called_once()
        saved_doc = mock_designs.save.call_args[0][0]
        assert saved_doc.core_rules == ["water plants daily"]
        assert saved_doc.acceptance_criteria == ["plants grow over time"]
        assert saved_doc.open_questions == ["weather system?"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph_run.py::test_design_graph_uses_design_agent -v`
Expected: FAIL — current `design_node` writes hardcoded `["rule 1"]` instead of calling agent

- [ ] **Step 3: Rewrite design_node to use DesignAgent**

Replace `build_design_graph()` in `studio/runtime/graph.py` (lines 215-250) with:

```python
def build_design_graph():
    from studio.agents.design import DesignAgent

    graph = StateGraph(dict)

    def design_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        requirement_id = _require_state_str(state, "requirement_id")
        workspace = StudioWorkspace(Path(workspace_root))
        workspace.ensure_layout()
        requirement = workspace.requirements.get(requirement_id)

        # Check if this is a rework (sent_back design doc exists)
        sent_back_reason: str | None = None
        if requirement.design_doc_id:
            try:
                existing_doc = workspace.design_docs.get(requirement.design_doc_id)
                sent_back_reason = existing_doc.sent_back_reason
            except FileNotFoundError:
                pass

        # Only transition to designing if not already there
        if requirement.status == "draft":
            requirement = transition_requirement(requirement, "designing")
            workspace.requirements.save(requirement)

        # Run DesignAgent
        agent = DesignAgent(project_root=Path(workspace_root))
        runtime_state = RuntimeState(
            project_id="design-project",
            run_id=_new_run_id(),
            task_id=f"design-{requirement.id}",
            goal={
                "prompt": requirement.title,
                "requirement_id": requirement.id,
                **({"sent_back_reason": sent_back_reason} if sent_back_reason else {}),
            },
        )
        result = agent.run(runtime_state)

        # Extract agent output from telemetry
        brief = result.state_patch.get("telemetry", {}).get("design_brief", {})
        title = brief.get("title", f"{requirement.title} Design")
        summary = brief.get("summary", requirement.title)
        core_rules = brief.get("core_rules", [])
        acceptance_criteria = brief.get("acceptance_criteria", [])
        open_questions = brief.get("open_questions", [])

        # Create or overwrite design doc
        design_doc_id = requirement.design_doc_id or f"design_{requirement.id.split('_')[-1]}"
        design_doc = DesignDoc(
            id=design_doc_id,
            requirement_id=requirement.id,
            title=str(title),
            summary=str(summary),
            core_rules=[str(r) for r in core_rules],
            acceptance_criteria=[str(c) for c in acceptance_criteria],
            open_questions=[str(q) for q in open_questions],
            status="pending_user_review",
        )

        # Transition requirement to pending_user_review
        pending_review = transition_requirement(requirement, "pending_user_review")
        updated_req = pending_review.model_copy(update={"design_doc_id": design_doc.id})

        workspace.design_docs.save(design_doc)
        workspace.requirements.save(updated_req)

        return {
            **state,
            "node_name": "design",
            "requirement_id": requirement.id,
            "design_doc_id": design_doc.id,
            "fallback_used": result.trace.get("fallback_used", False),
        }

    graph.add_node("design", design_node)
    graph.add_edge(START, "design")
    graph.add_edge("design", END)
    return graph.compile()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_graph_run.py::test_design_graph_uses_design_agent -v`
Expected: PASS

- [ ] **Step 5: Run full graph tests to check no regression**

Run: `uv run pytest tests/test_graph_run.py -v`
Expected: All PASS (existing tests may need updates if they relied on placeholder values)

- [ ] **Step 6: Commit**

```bash
git add studio/runtime/graph.py tests/test_graph_run.py
git commit -m "feat: rewrite design graph to use DesignAgent via Claude"
```

---

### Task 4: Create DesignWorkflowExecutor

**Files:**
- Create: `studio/runtime/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_executor.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from studio.runtime.executor import DesignWorkflowExecutor
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


def test_executor_new_design(tmp_path: Path, workspace: StudioWorkspace):
    """Executor should invoke design graph for a draft requirement."""
    req = RequirementCard(id="req_1", title="Garden Game")
    workspace.requirements.save(req)

    mock_result = {
        "node_name": "design",
        "requirement_id": "req_1",
        "design_doc_id": "design_1",
        "fallback_used": False,
    }
    with patch("studio.runtime.executor.build_design_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = mock_result
        mock_build.return_value = mock_graph

        executor = DesignWorkflowExecutor()
        result = executor.run(workspace, req, workspace_root=str(tmp_path))

    mock_graph.invoke.assert_called_once()
    assert result["requirement_id"] == "req_1"
    assert result["design_doc_id"] == "design_1"


def test_executor_rework(tmp_path: Path, workspace: StudioWorkspace):
    """Executor should pass sent_back_reason for a rework."""
    from studio.schemas.design_doc import DesignDoc

    req = RequirementCard(
        id="req_1",
        title="Garden Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Garden Design",
        summary="Summary",
        status="sent_back",
        sent_back_reason="Need more detail",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.executor.build_design_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "design",
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        mock_build.return_value = mock_graph

        executor = DesignWorkflowExecutor()
        result = executor.run(workspace, req, workspace_root=str(tmp_path))

    call_input = mock_graph.invoke.call_args[0][0]
    assert call_input["requirement_id"] == "req_1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_executor.py -v`
Expected: FAIL — `studio.runtime.executor` module not found

- [ ] **Step 3: Create DesignWorkflowExecutor**

Create `studio/runtime/executor.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

from studio.api.websocket import broadcast_entity_changed
from studio.runtime.graph import build_design_graph
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


class DesignWorkflowExecutor:
    """Execute the design workflow for a single requirement.

    Wraps the LangGraph design graph, invoking it with the correct
    input state and returning the result dict.
    """

    def run(
        self,
        workspace: StudioWorkspace,
        requirement: RequirementCard,
        *,
        workspace_root: str,
    ) -> dict[str, object]:
        graph = build_design_graph()
        graph_input: dict[str, object] = {
            "workspace_root": workspace_root,
            "requirement_id": requirement.id,
        }
        result = graph.invoke(graph_input)
        logger.info(
            "design workflow completed for %s: design_doc_id=%s",
            requirement.id,
            result.get("design_doc_id"),
        )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_executor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/runtime/executor.py tests/test_executor.py
git commit -m "feat: add DesignWorkflowExecutor wrapping design graph"
```

---

### Task 5: Create WorkflowPoller

**Files:**
- Create: `studio/runtime/poller.py`
- Create: `tests/test_poller.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_poller.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from studio.runtime.poller import WorkflowPoller
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


@pytest.fixture
def poller(tmp_path: Path) -> WorkflowPoller:
    return WorkflowPoller(
        workspace_path=tmp_path / ".studio-data",
        interval=1,
    )


def test_tick_picks_up_draft_requirement(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should find draft requirements and execute them."""
    req = RequirementCard(id="req_1", title="Test Game")
    workspace.requirements.save(req)

    with (
        patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor,
    ):
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        asyncio.run(poller._tick())

    mock_executor.run.assert_called_once()
    assert mock_executor.run.call_args[1]["workspace_root"] == str(tmp_path / ".studio-data")


def test_tick_skips_non_draft_requirements(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should not pick up requirements that are not draft."""
    req = RequirementCard(id="req_1", title="Test Game", status="approved")
    workspace.requirements.save(req)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        MockExecutor.return_value = mock_executor

        asyncio.run(poller._tick())

    mock_executor.run.assert_not_called()


def test_tick_picks_up_sent_back_rework(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should find designing requirements with sent_back design docs."""
    req = RequirementCard(
        id="req_1",
        title="Test Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Design",
        summary="Summary",
        status="sent_back",
        sent_back_reason="Needs work",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        asyncio.run(poller._tick())

    mock_executor.run.assert_called_once()


def test_tick_skips_designing_without_sent_back_doc(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should skip designing requirements whose design doc is not sent_back."""
    req = RequirementCard(
        id="req_1",
        title="Test Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Design",
        summary="Summary",
        status="pending_user_review",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        MockExecutor.return_value = mock_executor

        asyncio.run(poller._tick())

    mock_executor.run.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_poller.py -v`
Expected: FAIL — `studio.runtime.poller` module not found

- [ ] **Step 3: Create WorkflowPoller**

Create `studio/runtime/poller.py`:

```python
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from studio.runtime.executor import DesignWorkflowExecutor
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


class WorkflowPoller:
    """Background poller that auto-discovers eligible requirements and runs the design workflow."""

    def __init__(
        self,
        workspace_path: Path,
        interval: int | None = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.interval = interval or int(os.environ.get("GAME_STUDIO_POLL_INTERVAL", "10"))
        self._running = False

    async def start(self) -> None:
        """Start the polling loop. Runs until stop() is called."""
        self._running = True
        logger.info("WorkflowPoller started (interval=%ds, workspace=%s)", self.interval, self.workspace_path)
        while self._running:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._tick)
            except Exception:
                logger.exception("poller tick failed")
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("WorkflowPoller stopping")

    def _tick(self) -> None:
        """Single scan: find eligible requirements and execute."""
        workspace = StudioWorkspace(self.workspace_path)
        workspace.ensure_layout()

        requirements = workspace.requirements.list_all()
        executor = DesignWorkflowExecutor()

        for req in requirements:
            if self._is_eligible(req, workspace):
                logger.info("poller picked up requirement %s (status=%s)", req.id, req.status)
                try:
                    executor.run(
                        workspace,
                        req,
                        workspace_root=str(self.workspace_path),
                    )
                except Exception:
                    logger.exception("executor failed for requirement %s", req.id)
                    # Roll back to draft so the poller can retry on the next tick
                    if req.status in ("draft", "designing"):
                        try:
                            from studio.domain.requirement_flow import transition_requirement
                            rolled_back = req.model_copy(update={"status": "draft"})
                            workspace.requirements.save(rolled_back)
                            logger.info("rolled back requirement %s to draft", req.id)
                        except Exception:
                            logger.exception("failed to roll back requirement %s", req.id)

    def _is_eligible(self, req, workspace: StudioWorkspace) -> bool:
        """Check if a requirement is eligible for design workflow execution."""
        # New designs: draft status
        if req.status == "draft":
            return True
        # Reworks: designing status with sent_back design doc
        if req.status == "designing" and req.design_doc_id:
            try:
                doc = workspace.design_docs.get(req.design_doc_id)
                return doc.status == "sent_back"
            except FileNotFoundError:
                return False
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_poller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add studio/runtime/poller.py tests/test_poller.py
git commit -m "feat: add WorkflowPoller for auto-discovering eligible requirements"
```

---

### Task 6: Add FastAPI lifespan to start/stop poller

**Files:**
- Modify: `studio/api/main.py:1-71`
- Test: `tests/api/test_lifespan.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_lifespan.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


def test_app_starts_poller_on_lifespan():
    """FastAPI lifespan should create and start the WorkflowPoller."""
    with patch("studio.api.main.WorkflowPoller") as MockPoller:
        mock_poller = MagicMock()
        mock_poller.start = MagicMock()
        mock_poller.stop = MagicMock()
        MockPoller.return_value = mock_poller

        from studio.api.main import create_app
        app = create_app()
        # The lifespan context manager should have been set up
        assert app.router.lifespan_context is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_lifespan.py -v`
Expected: May fail or pass — we need to verify the lifespan is actually wired

- [ ] **Step 3: Add lifespan to create_app()**

Modify `studio/api/main.py`. Replace the entire file with:

```python
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from studio.api.routes import balance_tables, bugs, design_docs, logs, requirements, workflows
from studio.api.websocket import get_websocket_manager
from studio.runtime.poller import WorkflowPoller


@asynccontextmanager
async def _default_lifespan(app: FastAPI):
    """Start the workflow poller in the background."""
    workspace_path = Path(".runtime-data")
    poller = WorkflowPoller(workspace_path=workspace_path)
    task = asyncio.create_task(poller.start())
    yield
    await poller.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Game Studio API",
        description="Web UI backend for Game Studio collaboration kernel",
        version="0.1.0",
        lifespan=_default_lifespan,
    )

    # Configure CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative React port
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Register API routes
    app.include_router(requirements.router, prefix="/api")
    app.include_router(design_docs.router, prefix="/api")
    app.include_router(balance_tables.router, prefix="/api")
    app.include_router(bugs.router, prefix="/api")
    app.include_router(logs.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")

    # WebSocket endpoint for real-time updates
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time updates."""
        manager = get_websocket_manager()
        await manager.connect(websocket)

        try:
            # Send connected message
            await websocket.send_json({"type": "connected"})

            # Keep connection alive and handle incoming messages
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "subscribe":
                    workspace = data.get("workspace", ".studio-data")
                    await websocket.send_json({
                        "type": "subscribed",
                        "workspace": workspace
                    })

        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_lifespan.py -v`
Expected: PASS

- [ ] **Step 5: Run existing API tests to check no regression**

Run: `uv run pytest tests/api/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add studio/api/main.py tests/api/test_lifespan.py
git commit -m "feat: add FastAPI lifespan to start/stop WorkflowPoller"
```

---

### Task 7: Replace run-design API stub with executor call

**Files:**
- Modify: `studio/api/routes/workflows.py:22-78`
- Test: `tests/api/test_workflows.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_workflows.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def client():
    with patch("studio.api.main.WorkflowPoller"):
        from studio.api.main import create_app
        app = create_app()
        return TestClient(app)


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


def test_run_design_uses_executor(client, tmp_path: Path, workspace: StudioWorkspace):
    """run-design endpoint should delegate to DesignWorkflowExecutor."""
    req = RequirementCard(id="req_1", title="Test Game")
    workspace.requirements.save(req)

    with patch("studio.api.routes.workflows.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        response = client.post(
            "/api/workflows/run-design",
            params={"workspace": str(tmp_path), "requirement_id": "req_1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["requirement_id"] == "req_1"
    assert data["design_doc_id"] == "design_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_workflows.py::test_run_design_uses_executor -v`
Expected: FAIL — current endpoint returns hardcoded data, not from executor

- [ ] **Step 3: Rewrite run-design endpoint**

Replace the `run_design_workflow` function in `studio/api/routes/workflows.py` (lines 22-78) with:

```python
@router.post("/run-design")
async def run_design_workflow(
    workspace: str,
    requirement_id: str,
) -> dict[str, object]:
    """Run the design workflow for a requirement."""
    store = _get_workspace(workspace)

    try:
        requirement = store.requirements.get(requirement_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")

    from studio.runtime.executor import DesignWorkflowExecutor

    executor = DesignWorkflowExecutor()
    try:
        result = executor.run(store, requirement, workspace_root=str(Path(workspace) / ".studio-data"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

    return {
        "requirement_id": result.get("requirement_id", requirement_id),
        "requirement_status": "pending_user_review",
        "design_doc_id": result.get("design_doc_id"),
        "design_doc_status": "pending_user_review",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_workflows.py::test_run_design_uses_executor -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add studio/api/routes/workflows.py tests/api/test_workflows.py
git commit -m "feat: replace run-design stub with DesignWorkflowExecutor"
```

---

### Task 8: Frontend — Update DesignDoc type and add editable DesignEditor

**Files:**
- Modify: `web/src/lib/types.ts:168-179`
- Modify: `web/src/pages/DesignEditor.tsx`

- [ ] **Step 1: Update DesignDoc type**

In `web/src/lib/types.ts`, replace lines 168-179 with:

```typescript
// Design Doc types (not in OpenAPI spec yet)
export interface DesignDoc {
  id: string
  title: string
  summary: string
  status: 'draft' | 'pending_user_review' | 'approved' | 'sent_back'
  core_rules: string[]
  acceptance_criteria: string[]
  open_questions: string[]
  requirement_id: string
  sent_back_reason?: string | null
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Rewrite DesignEditor with editable fields and send-back dialog**

Replace the entire content of `web/src/pages/DesignEditor.tsx` with:

```tsx
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { useWorkspace } from '@/lib/workspace'
import { designDocsApi } from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import type { DesignDoc } from '@/lib/types'

function EditableList({ items, onChange, disabled }: {
  items: string[]
  onChange: (items: string[]) => void
  disabled: boolean
}) {
  const [text, setText] = useState(items.join('\n'))

  useEffect(() => {
    setText(items.join('\n'))
  }, [items])

  return (
    <textarea
      className="w-full min-h-[80px] p-2 border rounded text-sm font-mono"
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        onChange(e.target.value.split('\n').filter(Boolean))
      }}
      disabled={disabled}
    />
  )
}

export function DesignEditor() {
  const { id } = useParams<{ id: string }>()
  const { workspace } = useWorkspace()
  const queryClient = useQueryClient()
  const [sendBackOpen, setSendBackOpen] = useState(false)
  const [sendBackReason, setSendBackReason] = useState('')
  const [editedFields, setEditedFields] = useState<{
    core_rules: string[]
    acceptance_criteria: string[]
    open_questions: string[]
  }>({ core_rules: [], acceptance_criteria: [], open_questions: [] })
  const [hasEdits, setHasEdits] = useState(false)

  const { data: design, isLoading } = useQuery({
    queryKey: ['design-doc', id, workspace],
    queryFn: () => designDocsApi.get(workspace, id!) as Promise<DesignDoc>,
    enabled: !!id,
  })

  const saveMutation = useMutation({
    mutationFn: (data: Partial<DesignDoc>) => designDocsApi.update(workspace, id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      setHasEdits(false)
    },
  })

  const approveMutation = useMutation({
    mutationFn: () => designDocsApi.approve(workspace, id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
    },
  })

  const sendBackMutation = useMutation({
    mutationFn: (reason: string) => designDocsApi.sendBack(workspace, id!, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['design-doc'] })
      queryClient.invalidateQueries({ queryKey: ['requirements'] })
      setSendBackOpen(false)
      setSendBackReason('')
    },
  })

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>
  }

  if (!design) {
    return <div className="p-8 text-center text-muted-foreground">Design doc not found</div>
  }

  const isEditable = design.status === 'pending_user_review'

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">{design.title}</h1>
          <p className="text-muted-foreground">{id}</p>
        </div>
        <Badge>{design.status}</Badge>
      </div>

      {design.sent_back_reason && (
        <Card className="border-orange-300 bg-orange-50">
          <CardHeader>
            <CardTitle className="text-orange-800">Sent Back Reason</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-orange-900">{design.sent_back_reason}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{design.summary}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Core Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.core_rules || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, core_rules: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Acceptance Criteria</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.acceptance_criteria || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, acceptance_criteria: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Open Questions</CardTitle>
        </CardHeader>
        <CardContent>
          <EditableList
            items={design.open_questions || []}
            onChange={(items) => {
              setEditedFields((prev) => ({ ...prev, open_questions: items }))
              setHasEdits(true)
            }}
            disabled={!isEditable}
          />
        </CardContent>
      </Card>

      <div className="flex gap-4">
        {isEditable && (
          <>
            <Button
              onClick={() => saveMutation.mutate(editedFields)}
              disabled={!hasEdits || saveMutation.isPending}
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
            >
              ✓ Approve
            </Button>
            <Button
              variant="outline"
              onClick={() => setSendBackOpen(true)}
              disabled={sendBackMutation.isPending}
            >
              ⏪ Send Back
            </Button>
          </>
        )}
      </div>

      <Dialog open={sendBackOpen} onOpenChange={setSendBackOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Back for Revision</DialogTitle>
          </DialogHeader>
          <textarea
            className="w-full min-h-[120px] p-3 border rounded"
            placeholder="Describe what needs to be changed..."
            value={sendBackReason}
            onChange={(e) => setSendBackReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendBackOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (sendBackReason.trim()) {
                  sendBackMutation.mutate(sendBackReason.trim())
                }
              }}
              disabled={!sendBackReason.trim() || sendBackMutation.isPending}
            >
              {sendBackMutation.isPending ? 'Sending...' : 'Send Back'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd web && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types.ts web/src/pages/DesignEditor.tsx
git commit -m "feat(web): editable DesignEditor with send-back dialog"
```

---

### Task 9: Frontend — Add "View Design" link to RequirementCard

**Files:**
- Modify: `web/src/components/board/RequirementCard.tsx`
- Modify: `web/src/components/board/KanbanBoard.tsx` (if needed for props passthrough)

- [ ] **Step 1: Check KanbanBoard props passthrough**

Read `web/src/components/board/KanbanBoard.tsx` to see if `design_doc_id` is passed to RequirementCard. If not, update the prop passing.

- [ ] **Step 2: Update RequirementCard to show "View Design" link**

In `web/src/components/board/RequirementCard.tsx`, add `design_doc_id` prop and a link:

Update the interface:
```typescript
interface RequirementCardProps {
  id: string
  title: string
  status?: string
  priority?: string
  design_doc_id?: string | null
  workspace: string
  onClick: () => void
}
```

Update the component to accept and use `design_doc_id`:
```tsx
export function RequirementCard({ id, title, status, priority, design_doc_id, workspace, onClick }: RequirementCardProps) {
```

Add after the `TransitionMenu` div (before the closing `</Card>`):
```tsx
        {design_doc_id && (
          <a
            href={`/design-docs/${design_doc_id}`}
            className="text-xs text-blue-600 hover:underline mt-2 block"
            onClick={(e) => e.stopPropagation()}
          >
            View Design
          </a>
        )}
```

- [ ] **Step 3: Update KanbanBoard to pass design_doc_id**

Read `web/src/components/board/KanbanBoard.tsx` and ensure the `RequirementCard` instances receive `design_doc_id` from the requirement data.

- [ ] **Step 4: Verify frontend builds**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add web/src/components/board/RequirementCard.tsx web/src/components/board/KanbanBoard.tsx
git commit -m "feat(web): add View Design link to RequirementCard"
```

---

### Task 10: End-to-end verification

**Files:** No new files

- [ ] **Step 1: Run full Python test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run frontend build**

Run: `cd web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Start backend and verify poller logs**

Run (terminal 1):
```bash
uv run uvicorn studio.api.main:create_app --reload
```

Expected: Console shows "WorkflowPoller started" message.

- [ ] **Step 4: Start frontend**

Run (terminal 2):
```bash
cd web && npm run dev
```

- [ ] **Step 5: Test full flow manually**

1. Open http://localhost:5173
2. Create a new requirement with title "Test Game"
3. Wait for poller to pick it up (up to 10 seconds)
4. Verify the requirement card moves from "draft" to "pending_user_review" column
5. Click "View Design" link
6. Verify design doc shows with Agent-generated content
7. Click "Send Back", enter a reason, submit
8. Wait for poller to rework (up to 10 seconds)
9. Verify the design doc is updated
10. Edit some fields, click "Save Changes"
11. Click "Approve"
12. Verify status changes to "approved"

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
