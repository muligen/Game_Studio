# Project Agent Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-level session layer so each managed agent keeps a Claude Agent SDK session across workflows and user debug.

**Architecture:** A `ProjectAgentSession` schema stored via `JsonRepository` in workspace. A `SessionRegistry` service creates/finds sessions by `project_id + agent`. `ClaudeRoleAdapter` gains an optional `session_id` parameter that flows into `ClaudeAgentOptions.session_id`. The meeting graph looks up sessions before calling agents. The CLI `agent chat` gains `--project-id` to attach to a stored session.

**Tech Stack:** Python 3.12, Pydantic, Claude Agent SDK (`ClaudeAgentOptions.session_id`, `continue_conversation`, `resume`), Typer CLI

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `studio/schemas/session.py` | Create | `ProjectAgentSession` Pydantic model |
| `studio/storage/session_registry.py` | Create | `SessionRegistry` — create, find, touch session records |
| `studio/storage/workspace.py` | Modify | Add `sessions` repository + ensure_layout dir |
| `studio/llm/claude_roles.py` | Modify | Add `session_id` to `ClaudeRoleAdapter`, flow into `ClaudeAgentOptions` |
| `studio/runtime/graph.py` | Modify | Meeting graph: look up sessions before agent calls |
| `studio/interfaces/cli.py` | Modify | Add `--project-id` to `agent chat`, session-aware chat and verbose output |
| `tests/test_session_schemas.py` | Create | Schema validation tests |
| `tests/test_session_registry.py` | Create | Registry CRUD tests |
| `tests/test_session_claude_roles.py` | Create | Session flow into ClaudeAgentOptions tests |
| `tests/test_session_cli.py` | Create | CLI `--project-id` tests |
| `tests/test_session_meeting_graph.py` | Create | Meeting graph uses project sessions |

---

### Task 1: ProjectAgentSession Schema

**Files:**
- Create: `studio/schemas/session.py`
- Test: `tests/test_session_schemas.py`

- [ ] **Step 1: Write schema tests**

```python
# tests/test_session_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.session import ProjectAgentSession


def test_session_requires_project_id_agent_session_id():
    s = ProjectAgentSession(
        project_id="proj_123",
        requirement_id="req_456",
        agent="qa",
        session_id="claude-session-abc",
    )
    assert s.project_id == "proj_123"
    assert s.agent == "qa"
    assert s.session_id == "claude-session-abc"
    assert s.status == "active"


def test_session_rejects_empty_project_id():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="",
            requirement_id="req_1",
            agent="dev",
            session_id="sid",
        )


def test_session_rejects_empty_agent():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="",
            session_id="sid",
        )


def test_session_rejects_empty_session_id():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="dev",
            session_id="",
        )


def test_session_composite_id():
    s = ProjectAgentSession(
        project_id="proj_abc",
        requirement_id="req_1",
        agent="design",
        session_id="sid-1",
    )
    assert s.composite_id == "proj_abc_design"


def test_session_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="dev",
            session_id="sid",
            unknown="oops",
        )


def test_session_created_at_is_auto_set():
    s = ProjectAgentSession(
        project_id="proj_1",
        requirement_id="req_1",
        agent="dev",
        session_id="sid",
    )
    assert s.created_at is not None
    assert s.last_used_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_schemas.py -v`
Expected: FAIL — `studio.schemas.session` does not exist

- [ ] **Step 3: Write the schema**

```python
# studio/schemas/session.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


SessionStatus = Literal["active", "expired"]


class ProjectAgentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    session_id: StrippedNonEmptyStr
    status: SessionStatus = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_used_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def composite_id(self) -> str:
        return f"{self.project_id}_{self.agent}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_schemas.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/schemas/session.py tests/test_session_schemas.py
git commit -m "feat: add ProjectAgentSession schema"
```

---

### Task 2: SessionRegistry Service

**Files:**
- Create: `studio/storage/session_registry.py`
- Test: `tests/test_session_registry.py`

- [ ] **Step 1: Write registry tests**

```python
# tests/test_session_registry.py
from __future__ import annotations

from pathlib import Path

import pytest

from studio.schemas.session import ProjectAgentSession
from studio.storage.session_registry import SessionRegistry


def test_create_stores_session(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    s = registry.create("proj_1", "req_1", "dev", "session-abc")
    assert s.project_id == "proj_1"
    assert s.agent == "dev"
    assert s.session_id == "session-abc"
    assert s.status == "active"


def test_create_persists_to_disk(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "dev", "session-abc")
    loaded = registry.find("proj_1", "dev")
    assert loaded is not None
    assert loaded.session_id == "session-abc"


def test_find_returns_none_when_missing(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    assert registry.find("proj_999", "qa") is None


def test_find_returns_session_when_exists(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "qa", "session-xyz")
    found = registry.find("proj_1", "qa")
    assert found is not None
    assert found.session_id == "session-xyz"


def test_touch_updates_last_used_at(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "dev", "session-abc")
    original = registry.find("proj_1", "dev")
    assert original is not None
    import time
    time.sleep(0.01)
    registry.touch("proj_1", "dev")
    updated = registry.find("proj_1", "dev")
    assert updated is not None
    assert updated.last_used_at != original.last_used_at


def test_touch_raises_when_missing(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    with pytest.raises(FileNotFoundError, match="project agent session not found"):
        registry.touch("proj_999", "qa")


def test_create_all_agents_creates_one_per_managed_agent(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    managed_agents = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
    sessions = registry.create_all("proj_1", "req_1", managed_agents)
    assert len(sessions) == 7
    for agent in managed_agents:
        found = registry.find("proj_1", agent)
        assert found is not None
        assert found.agent == agent


def test_create_all_agents_uses_unique_session_ids(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    managed_agents = ["moderator", "design", "dev"]
    sessions = registry.create_all("proj_1", "req_1", managed_agents)
    session_ids = [s.session_id for s in sessions]
    assert len(set(session_ids)) == len(session_ids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_registry.py -v`
Expected: FAIL — `studio.storage.session_registry` does not exist

- [ ] **Step 3: Write the SessionRegistry**

```python
# studio/storage/session_registry.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from studio.schemas.session import ProjectAgentSession
from studio.storage.base import JsonRepository


class SessionRegistry:
    def __init__(self, root: Path) -> None:
        self._repo = JsonRepository(root / "project_agent_sessions", ProjectAgentSession)

    def create(self, project_id: str, requirement_id: str, agent: str, session_id: str) -> ProjectAgentSession:
        record = ProjectAgentSession(
            project_id=project_id,
            requirement_id=requirement_id,
            agent=agent,
            session_id=session_id,
        )
        return self._repo.save(record)

    def find(self, project_id: str, agent: str) -> ProjectAgentSession | None:
        composite_id = f"{project_id}_{agent}"
        try:
            return self._repo.get(composite_id)
        except (FileNotFoundError, ValueError):
            return None

    def touch(self, project_id: str, agent: str) -> ProjectAgentSession:
        composite_id = f"{project_id}_{agent}"
        record = self._repo.get(composite_id)
        updated = record.model_copy(update={"last_used_at": datetime.now(UTC).isoformat()})
        return self._repo.save(updated)

    def create_all(self, project_id: str, requirement_id: str, agents: Sequence[str]) -> list[ProjectAgentSession]:
        sessions: list[ProjectAgentSession] = []
        for agent in agents:
            session_id = f"{project_id}_{agent}_{uuid.uuid4().hex[:12]}"
            sessions.append(self.create(project_id, requirement_id, agent, session_id))
        return sessions
```

Note: `ProjectAgentSession.composite_id` is a computed property, not an `id` field. The `JsonRepository.save()` requires an `id` field in the payload. We need to add an `id` field to `ProjectAgentSession` or adjust the approach.

The fix: add `id` as a field that defaults to `f"{project_id}_{agent}"`:

Update `studio/schemas/session.py` — replace the `composite_id` property with an `id` field:

```python
class ProjectAgentSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    project_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    session_id: StrippedNonEmptyStr
    status: SessionStatus = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_used_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = f"{self.project_id}_{self.agent}"
```

Also update the test — replace `test_session_composite_id` with:

```python
def test_session_id_defaults_to_project_agent():
    s = ProjectAgentSession(
        project_id="proj_abc",
        requirement_id="req_1",
        agent="design",
        session_id="sid-1",
    )
    assert s.id == "proj_abc_design"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_registry.py tests/test_session_schemas.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/storage/session_registry.py tests/test_session_registry.py studio/schemas/session.py tests/test_session_schemas.py
git commit -m "feat: add SessionRegistry for project-agent session management"
```

---

### Task 3: Add `session_id` to `ClaudeRoleAdapter`

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Test: `tests/test_session_claude_roles.py`

The `ClaudeRoleAdapter.__init__` currently takes `(project_root, profile)`. We add an optional `session_id` parameter. When set, it flows into `ClaudeAgentOptions(session_id=..., continue_conversation=True)` in both `_generate_payload()` and `_chat()`.

- [ ] **Step 1: Write session integration tests**

```python
# tests/test_session_claude_roles.py
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from studio.llm.claude_roles import ClaudeRoleAdapter, ClaudeRoleConfig


def test_adapter_stores_session_id():
    adapter = ClaudeRoleAdapter(session_id="sess-123")
    assert adapter.session_id == "sess-123"


def test_adapter_defaults_session_id_to_none():
    adapter = ClaudeRoleAdapter()
    assert adapter.session_id is None


@pytest.mark.anyio
async def test_generate_payload_passes_session_id_to_sdk_options(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        from claude_agent_sdk import ResultMessage
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-123",
            structured_output={
                "agenda": ["test"],
                "attendees": ["dev"],
                "focus_questions": [],
            },
        )

    import studio.llm.claude_roles as cr_module
    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(
        session_id="sess-123",
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        adapter,
        "load_config",
        lambda: ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None),
    )

    adapter.generate("moderator_prepare", {"goal": {"prompt": "test"}})
    opts = captured_options["options"]
    assert opts.session_id == "sess-123"
    assert opts.continue_conversation is True


@pytest.mark.anyio
async def test_generate_payload_omits_session_id_when_none(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        from claude_agent_sdk import ResultMessage
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="new",
            structured_output={
                "agenda": ["test"],
                "attendees": ["dev"],
                "focus_questions": [],
            },
        )

    import studio.llm.claude_roles as cr_module
    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(project_root=tmp_path)
    monkeypatch.setattr(
        adapter,
        "load_config",
        lambda: ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None),
    )

    adapter.generate("moderator_prepare", {"goal": {"prompt": "test"}})
    opts = captured_options["options"]
    assert opts.session_id is None
    assert opts.continue_conversation is False


@pytest.mark.anyio
async def test_chat_passes_session_id_to_sdk_options(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        from claude_agent_sdk import ResultMessage
        yield ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-123",
            result="chat reply",
        )

    import studio.llm.claude_roles as cr_module
    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(session_id="sess-123", project_root=tmp_path)
    monkeypatch.setattr(
        adapter,
        "load_config",
        lambda: ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None),
    )

    result = adapter.chat("hello")
    assert result == "chat reply"
    opts = captured_options["options"]
    assert opts.session_id == "sess-123"
    assert opts.continue_conversation is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_claude_roles.py -v`
Expected: FAIL — `ClaudeRoleAdapter` does not accept `session_id`

- [ ] **Step 3: Modify `ClaudeRoleAdapter.__init__` to accept `session_id`**

In `studio/llm/claude_roles.py`, find the `ClaudeRoleAdapter.__init__` method and add `session_id` parameter:

```python
class ClaudeRoleAdapter:
    def __init__(
        self,
        project_root: Path | None = None,
        profile: ClaudeAdapterProfile | None = None,
        session_id: str | None = None,
    ) -> None:
        self.project_root = _repo_root_from(project_root)
        self.profile = profile
        self.session_id = session_id
        self._env_path = self.project_root / ".env"
        self._last_debug_record: dict[str, object] | None = None
```

- [ ] **Step 4: Pass `session_id` and `continue_conversation` in `_generate_payload`**

In the `_generate_payload` method, update the `ClaudeAgentOptions` construction:

```python
        options = ClaudeAgentOptions(
            cwd=self._claude_project_root(),
            model=config.model,
            tools=[] if config.mode == "text" else None,
            permission_mode="default",
            setting_sources=["project"],
            env=self._sdk_env(config),
            output_format=self._output_format(role_name),
            session_id=self.session_id,
            continue_conversation=self.session_id is not None,
        )
```

- [ ] **Step 5: Pass `session_id` and `continue_conversation` in `_chat`**

In the `_chat` method, update the `ClaudeAgentOptions` construction:

```python
        options = ClaudeAgentOptions(
            cwd=self._claude_project_root(),
            model=config.model,
            tools=[] if config.mode == "text" else None,
            permission_mode="default",
            setting_sources=["project"],
            env=self._sdk_env(config),
            session_id=self.session_id,
            continue_conversation=self.session_id is not None,
        )
```

- [ ] **Step 6: Also update `_generate_payload_via_subprocess` if it constructs options**

Search for any other `ClaudeAgentOptions` constructions in the file and add the same `session_id`/`continue_conversation` parameters.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_claude_roles.py tests/test_claude_roles.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 9: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/llm/claude_roles.py tests/test_session_claude_roles.py
git commit -m "feat: add session_id support to ClaudeRoleAdapter"
```

---

### Task 4: Add `sessions` Repository to Workspace

**Files:**
- Modify: `studio/storage/workspace.py`

- [ ] **Step 1: Add import and repository**

Read `studio/storage/workspace.py`. Add:

```python
from studio.schemas.session import ProjectAgentSession
```

Add to `StudioWorkspace.__init__` after existing repositories:

```python
        self.sessions = JsonRepository(root / "project_agent_sessions", ProjectAgentSession)
```

Add `self.sessions.root` to the `ensure_layout` tuple.

- [ ] **Step 2: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 3: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/storage/workspace.py
git commit -m "feat: add sessions repository to StudioWorkspace"
```

---

### Task 5: Meeting Graph Uses Project Sessions

**Files:**
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_session_meeting_graph.py`

When `project_id` is present in graph state, the meeting graph nodes look up the agent's session from `SessionRegistry` and pass `session_id` into the agent's `ClaudeRoleAdapter`.

- [ ] **Step 1: Write session-meeting-graph tests**

```python
# tests/test_session_meeting_graph.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from studio.runtime.graph import build_meeting_graph
from studio.schemas.requirement import RequirementCard
from studio.schemas.session import ProjectAgentSession
from studio.storage.session_registry import SessionRegistry
from studio.storage.workspace import StudioWorkspace


_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _disable_live_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "studio.llm.claude_worker.ClaudeWorkerAdapter.load_config",
        lambda self: type("Config", (), {"enabled": False, "mode": "text", "model": None, "api_key": None, "base_url": None})(),
    )
    monkeypatch.setattr(
        "studio.llm.claude_roles.ClaudeRoleAdapter.load_config",
        lambda self: type("Config", (), {"enabled": False, "mode": "text", "model": None, "api_key": None, "base_url": None})(),
    )


def _setup_workspace(tmp_path: Path) -> tuple[StudioWorkspace, str]:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Design a puzzle game"))
    return workspace, str(workspace_root)


def test_meeting_graph_without_project_id_uses_no_session(tmp_path: Path):
    workspace, workspace_root = _setup_workspace(tmp_path)

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": workspace_root,
        "project_root": str(tmp_path),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
    })

    assert result["node_name"] == "moderator_minutes"
    assert "minutes" in result


def test_meeting_graph_with_project_id_looks_up_sessions(tmp_path: Path):
    workspace, workspace_root = _setup_workspace(tmp_path)

    # Create sessions
    registry = SessionRegistry(Path(workspace_root))
    registry.create("proj_1", "req_001", "moderator", "mod-session-123")
    registry.create("proj_1", "req_001", "design", "design-session-456")
    registry.create("proj_1", "req_001", "dev", "dev-session-789")
    registry.create("proj_1", "req_001", "qa", "qa-session-012")

    created_session_ids: list[str | None] = []

    original_init = __import__("studio.llm.claude_roles", fromlist=["ClaudeRoleAdapter"]).ClaudeRoleAdapter.__init__

    def tracking_init(self, **kwargs):
        created_session_ids.append(kwargs.get("session_id"))
        return original_init(self, **kwargs)

    with patch("studio.llm.claude_roles.ClaudeRoleAdapter.__init__", tracking_init):
        graph = build_meeting_graph()
        result = graph.invoke({
            "workspace_root": workspace_root,
            "project_root": str(tmp_path),
            "requirement_id": "req_001",
            "user_intent": "Design a puzzle game",
            "project_id": "proj_1",
        })

    assert result["node_name"] == "moderator_minutes"
    # At least moderator and agent sessions should be injected
    non_none = [s for s in created_session_ids if s is not None]
    assert len(non_none) > 0


def test_meeting_graph_with_project_id_missing_session_uses_no_session(tmp_path: Path):
    workspace, workspace_root = _setup_workspace(tmp_path)

    # Create only moderator session, not agent sessions
    registry = SessionRegistry(Path(workspace_root))
    registry.create("proj_1", "req_001", "moderator", "mod-session-123")

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": workspace_root,
        "project_root": str(tmp_path),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
        "project_id": "proj_1",
    })

    # Should still complete — missing sessions are not errors
    assert result["node_name"] == "moderator_minutes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_meeting_graph.py -v`
Expected: FAIL — graph does not look up sessions yet

- [ ] **Step 3: Modify `build_meeting_graph()` to look up sessions**

Read `studio/runtime/graph.py` and find the `build_meeting_graph()` function. The key changes:

1. Add `from studio.storage.session_registry import SessionRegistry` inside the function.

2. Add `"project_id": str` to the `_MeetingState` TypedDict.

3. Create a helper function inside `build_meeting_graph()`:

```python
    def _session_id_for(state: _MeetingState, agent_role: str) -> str | None:
        pid = state.get("project_id")
        if not pid:
            return None
        ws_root = state.get("workspace_root")
        if not ws_root:
            return None
        reg = SessionRegistry(Path(str(ws_root)))
        rec = reg.find(str(pid), agent_role)
        if rec is None:
            return None
        reg.touch(str(pid), agent_role)
        return rec.session_id
```

4. In `moderator_prepare_node`, use session when creating `ModeratorAgent`:

Change:
```python
        moderator = ModeratorAgent(project_root=Path(project_root))
```
To:
```python
        session_id = _session_id_for(state, "moderator")
        moderator = ModeratorAgent(
            project_root=Path(project_root),
            session_id=session_id,
        )
```

5. In `agent_opinion_node`, use session when creating the agent:

Change:
```python
        agent = agent_cls(project_root=Path(project_root))
```
To:
```python
        session_id = _session_id_for(state, target_role)
        agent = agent_cls(
            project_root=Path(project_root),
            session_id=session_id,
        )
```

6. In `moderator_summarize_node` and `moderator_minutes_node`, same pattern for the moderator.

- [ ] **Step 4: Modify agent constructors to accept `session_id`**

Each agent (`DesignAgent`, `ModeratorAgent`, `DevAgent`, `QaAgent`, `ArtAgent`) needs to accept and forward `session_id`. The pattern for each agent:

In `studio/agents/design.py`, `studio/agents/moderator.py`, `studio/agents/dev.py`, `studio/agents/qa.py`, `studio/agents/art.py`:

```python
class XxxAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
        session_id: str | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader(repo_root=project_root).load("xxx")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root, profile=profile, session_id=session_id
        )
```

Do this for all 5 agents: `design`, `dev`, `qa`, `art`, `moderator`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_meeting_graph.py tests/test_meeting_graph.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/runtime/graph.py studio/agents/design.py studio/agents/dev.py studio/agents/qa.py studio/agents/art.py studio/agents/moderator.py tests/test_session_meeting_graph.py
git commit -m "feat: meeting graph uses project sessions when available"
```

---

### Task 6: CLI `--project-id` Support for `agent chat`

**Files:**
- Modify: `studio/interfaces/cli.py`
- Test: `tests/test_session_cli.py`

- [ ] **Step 1: Write CLI session tests**

```python
# tests/test_session_cli.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from studio.interfaces.cli import app
from studio.schemas.session import ProjectAgentSession
from studio.storage.session_registry import SessionRegistry


def _setup_sessions(workspace_root: Path, project_id: str, requirement_id: str, agent: str, session_id: str) -> None:
    registry = SessionRegistry(workspace_root)
    registry.create(project_id, requirement_id, agent, session_id)


def test_agent_chat_with_project_id_passes_session_id(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / ".studio-data"
    workspace.mkdir()
    _setup_sessions(workspace, "proj_1", "req_1", "qa", "session-abc")

    captured_session_ids: list[str | None] = []

    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None):
            pass

        def load(self, agent_name: str) -> FakeProfile:
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root=None, profile=None, session_id=None):
            captured_session_ids.append(session_id)

        def chat(self, message: str) -> str:
            return "project-aware reply"

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "hello",
         "--project-id", "proj_1", "--workspace", str(workspace.parent)],
    )

    assert result.exit_code == 0
    assert captured_session_ids == ["session-abc"]


def test_agent_chat_with_project_id_fails_when_session_missing(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / ".studio-data"
    workspace.mkdir()

    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root=None):
            pass

        def load(self, agent_name: str):
            return FakeProfile()

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "hello",
         "--project-id", "proj_999", "--workspace", str(workspace.parent)],
    )

    assert result.exit_code != 0
    assert "project agent session not found" in result.stderr


def test_agent_chat_verbose_with_project_id_shows_session_id(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / ".studio-data"
    workspace.mkdir()
    _setup_sessions(workspace, "proj_1", "req_1", "qa", "session-xyz")

    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root=None):
            pass

        def load(self, agent_name: str):
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root=None, profile=None, session_id=None):
            pass

        def chat(self, message: str) -> str:
            return "verbose reply"

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "hello",
         "--project-id", "proj_1", "--workspace", str(workspace.parent),
         "--verbose"],
    )

    assert result.exit_code == 0
    assert "session-xyz" in result.stdout
    assert "proj_1" in result.stdout


def test_agent_chat_without_project_id_works_as_before(monkeypatch, tmp_path: Path) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root=None):
            pass

        def load(self, agent_name: str):
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root=None, profile=None, session_id=None):
            assert session_id is None

        def chat(self, message: str) -> str:
            return "normal reply"

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "hello"],
    )

    assert result.exit_code == 0
    assert "normal reply" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_cli.py -v`
Expected: FAIL — `--project-id` and `--workspace` options don't exist on `agent chat`

- [ ] **Step 3: Add `--project-id` and `--workspace` to `agent_chat` command**

In `studio/interfaces/cli.py`, modify the `agent_chat` function:

```python
@agent_app.command("chat")
def agent_chat(
    agent: str = typer.Option(..., "--agent", help="Managed agent profile name"),
    message: str | None = typer.Option(None, "--message", help="Single-turn user message"),
    interactive: bool = typer.Option(False, "--interactive", help="Start a simple REPL"),
    verbose: bool = typer.Option(False, "--verbose", help="Print debug metadata before the reply"),
    project_id: str | None = typer.Option(None, "--project-id", help="Use project agent session"),
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root (required with --project-id)"),
) -> None:
    if not interactive and not message:
        _fail_cli("--message is required unless --interactive is set")

    if project_id and not workspace:
        _fail_cli("--workspace is required when --project-id is set")

    try:
        loader = AgentProfileLoader()
        profile = loader.load(agent)
    except AgentProfileError as exc:
        _fail_cli(str(exc))

    # Resolve session_id from project
    session_id: str | None = None
    if project_id:
        from studio.storage.session_registry import SessionRegistry

        ws_root = workspace / ".studio-data" if workspace else None
        if ws_root is None:
            _fail_cli("--workspace is required when --project-id is set")
        registry = SessionRegistry(ws_root)
        record = registry.find(project_id, agent)
        if record is None:
            _fail_cli(f"project agent session not found: {project_id}/{agent}")
        session_id = record.session_id
        registry.touch(project_id, agent)

    if verbose:
        debug_info = {
            "agent": agent,
            "profile_path": str(_profile_path(loader, agent)),
            "claude_project_root": str(profile.claude_project_root),
            "system_prompt": profile.system_prompt,
        }
        if session_id:
            debug_info["project_id"] = project_id
            debug_info["session_id"] = session_id
        typer.echo(json.dumps(debug_info, indent=2, ensure_ascii=False))

    try:
        if interactive:
            runner = ClaudeRoleAdapter(profile=profile, session_id=session_id)
            while True:
                user_input = typer.prompt(f"{agent}>")
                if user_input.strip().lower() in {"exit", "quit"}:
                    return
                _echo_agent_reply(runner.chat(user_input))
            return

        runner = ClaudeRoleAdapter(profile=profile, session_id=session_id)
        _echo_agent_reply(runner.chat(message or ""))
    except ClaudeRoleError as exc:
        _fail_cli(str(exc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_cli.py tests/test_agent_chat_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/interfaces/cli.py tests/test_session_cli.py
git commit -m "feat: add --project-id session support to agent chat CLI"
```

---

### Task 7: Kickoff Command (CLI Entry Point)

**Files:**
- Modify: `studio/interfaces/cli.py`
- Test: `tests/test_session_cli.py` (extend)

This adds a `project kickoff` CLI command that creates project-agent sessions and runs the meeting graph with them.

- [ ] **Step 1: Write kickoff tests**

Add to `tests/test_session_cli.py`:

```python
def test_project_kickoff_creates_sessions_and_runs_meeting(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / ".studio-data"
    from studio.storage.workspace import StudioWorkspace
    ws = StudioWorkspace(workspace)
    ws.ensure_layout()
    ws.requirements.save(
        __import__("studio.schemas.requirement", fromlist=["RequirementCard"]).RequirementCard(
            id="req_001", title="Design a card game"
        )
    )

    meeting_result = {
        "node_name": "moderator_minutes",
        "minutes": {"id": "meeting_001", "requirement_id": "req_001", "title": "Kickoff"},
    }

    class FakeGraph:
        def invoke(self, state):
            return {**state, **meeting_result}

    monkeypatch.setattr("studio.interfaces.cli.build_meeting_graph", lambda: FakeGraph())

    result = CliRunner().invoke(
        app,
        ["project", "kickoff", "--workspace", str(tmp_path),
         "--requirement-id", "req_001", "--user-intent", "Design a card game"],
    )

    assert result.exit_code == 0
    assert "proj_" in result.stdout

    # Verify sessions were created
    from studio.storage.session_registry import SessionRegistry
    reg = SessionRegistry(workspace)
    for agent in ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]:
        found = reg.find(result.stdout.strip().split()[0], agent)
        assert found is not None, f"session missing for {agent}"


def test_project_kickoff_fails_without_workspace(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["project", "kickoff"],
    )
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_cli.py::test_project_kickoff_creates_sessions_and_runs_meeting -v`
Expected: FAIL — `project kickoff` command does not exist

- [ ] **Step 3: Add `project` CLI sub-app and `kickoff` command**

In `studio/interfaces/cli.py`, add a new Typer sub-app and the kickoff command:

```python
project_app = typer.Typer(help="Project management commands")
app.add_typer(project_app, name="project")


@project_app.command("kickoff")
def project_kickoff(
    workspace: Path = typer.Option(..., "--workspace", "-w", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement to kick off"),
    user_intent: str | None = typer.Option(None, "--user-intent", help="Override user intent"),
) -> None:
    from studio.runtime.graph import build_meeting_graph
    from studio.storage.session_registry import SessionRegistry
    from studio.storage.workspace import StudioWorkspace

    ws_root = workspace / ".studio-data"
    ws = StudioWorkspace(ws_root)
    requirement = ws.requirements.get(requirement_id)
    intent = user_intent or requirement.title

    project_id = f"proj_{uuid.uuid4().hex[:8]}"

    managed_agents = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
    registry = SessionRegistry(ws_root)
    registry.create_all(project_id, requirement_id, managed_agents)

    project_root = str(workspace.parent.parent) if ws_root.name == ".studio-data" else str(workspace)

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(ws_root),
        "project_root": project_root,
        "requirement_id": requirement_id,
        "user_intent": intent,
        "project_id": project_id,
    })

    typer.echo(f"{project_id} kickoff_complete")
```

Add `import uuid` at the top of the file if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/test_session_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/project-agent-session && python -m pytest tests/ --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/project-agent-session
git add studio/interfaces/cli.py tests/test_session_cli.py
git commit -m "feat: add project kickoff command with session creation"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Data model (ProjectAgentSession) → Task 1
  - Session registry (create, find, touch) → Task 2
  - Claude SDK session_id flow → Task 3
  - Workspace integration → Task 4
  - Meeting graph uses sessions → Task 5
  - CLI debug entry (--project-id) → Task 6
  - Kickoff action → Task 7
  - Managed agents list (7 agents) → Task 7
  - Error handling (missing session) → Tasks 2, 6
  - Testing requirements (all 6 spec tests) → covered across Tasks 1-7

- [x] **Placeholder scan:** No TBD/TODO/placeholder steps. All code blocks contain complete implementations.

- [x] **Type consistency:**
  - `ProjectAgentSession.id` defaults to `f"{project_id}_{agent}"` — matches `JsonRepository.save()` requirement
  - `session_id: str | None` parameter consistent across `ClaudeRoleAdapter.__init__`, agent constructors, and CLI
  - `_MeetingState` TypedDict has `project_id: str` field
  - `SessionRegistry.find()` returns `ProjectAgentSession | None` — callers check for `None`
