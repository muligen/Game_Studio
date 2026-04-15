# Claude Workflow Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stub workflow agents with Claude Agent SDK-backed implementations that keep deterministic fallback behavior and preserve the current CLI and graph contracts.

**Architecture:** Add a shared role-based Claude adapter under `studio/llm` that owns config loading, Claude invocation, structured output parsing, and subprocess fallback. Keep `planner` deterministic and keep per-agent responsibilities focused on runtime input extraction, `NodeResult` mapping, and deterministic fallback payloads.

**Tech Stack:** Python 3.12, Pydantic v2, Typer, LangGraph, Claude Agent SDK, pytest

---

## File Structure

- Create: `studio/llm/claude_roles.py`
  Responsibility: shared role-based Claude adapter, role payload models, prompt builders, structured parsing, subprocess fallback.
- Modify: `studio/llm/__init__.py`
  Responsibility: export the new adapter and role payload models.
- Modify: `studio/llm/claude_worker.py`
  Responsibility: keep backward-compatible worker API while delegating to shared role infrastructure.
- Modify: `studio/agents/worker.py`
  Responsibility: consume the shared role adapter without changing the existing external behavior.
- Modify: `studio/agents/reviewer.py`
  Responsibility: replace stub logic with Claude-backed review plus deterministic fallback.
- Modify: `studio/agents/design.py`
  Responsibility: replace stub logic with Claude-backed design drafting plus deterministic fallback.
- Modify: `studio/agents/dev.py`
  Responsibility: replace stub logic with Claude-backed implementation summary plus deterministic fallback.
- Modify: `studio/agents/qa.py`
  Responsibility: replace stub logic with Claude-backed QA summary plus deterministic fallback.
- Modify: `studio/agents/quality.py`
  Responsibility: replace stub logic with Claude-backed quality summary plus deterministic fallback.
- Modify: `studio/agents/art.py`
  Responsibility: replace stub logic with Claude-backed art direction summary plus deterministic fallback.
- Test: `tests/test_claude_roles.py`
  Responsibility: validate shared adapter payload parsing, role prompts, and error handling.
- Modify: `tests/test_claude_worker.py`
  Responsibility: preserve worker behavior while proving it now runs on the shared role adapter path.
- Create: `tests/test_role_agents.py`
  Responsibility: cover success and fallback behavior for reviewer, design, dev, qa, quality, and art agents.
- Modify: `tests/test_graph_run.py`
  Responsibility: update assertions if any trace or payload details change through the new adapter.
- Modify: `tests/test_agent_adapters.py`
  Responsibility: extend adapter coverage if dispatcher behavior or import fallback paths are affected.

### Task 1: Add Shared Role Payload Models and Parsing Tests

**Files:**
- Create: `tests/test_claude_roles.py`
- Modify: `studio/llm/__init__.py`
- Create: `studio/llm/claude_roles.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.llm.claude_roles import (
    ClaudeRoleAdapter,
    ClaudeRoleError,
    ReviewerPayload,
    parse_role_payload,
)


def test_parse_role_payload_validates_reviewer_output() -> None:
    payload = parse_role_payload(
        "reviewer",
        {"decision": "continue", "reason": "looks good", "risks": ["minor polish"]},
    )

    assert isinstance(payload, ReviewerPayload)
    assert payload.decision == "continue"
    assert payload.reason == "looks good"
    assert payload.risks == ["minor polish"]


def test_parse_role_payload_rejects_invalid_reviewer_output() -> None:
    try:
        parse_role_payload("reviewer", {"decision": "ship-it"})
    except ClaudeRoleError as exc:
        assert str(exc) == "invalid_claude_output"
    else:
        raise AssertionError("expected ClaudeRoleError")


def test_role_prompt_mentions_role_contract() -> None:
    prompt = ClaudeRoleAdapter._prompt(
        "qa",
        {"feature": "photo mode", "requirement_id": "req_001"},
    )

    assert "qa" in prompt.lower()
    assert "passed" in prompt
    assert "suggested_bug" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_roles.py -v`
Expected: FAIL with `ModuleNotFoundError` or import error for `studio.llm.claude_roles`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ClaudeRoleError(RuntimeError):
    pass


class ReviewerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["continue", "retry"]
    reason: str
    risks: list[str] = Field(default_factory=list)


ROLE_MODELS = {"reviewer": ReviewerPayload}


def parse_role_payload(role_name: str, data: object) -> BaseModel:
    model_type = ROLE_MODELS[role_name]
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise ClaudeRoleError("invalid_claude_output") from exc


@dataclass
class ClaudeRoleAdapter:
    @staticmethod
    def _prompt(role_name: str, context: dict[str, object]) -> str:
        return (
            f"You are the {role_name} agent.\n"
            f"Return structured output for role {role_name}.\n"
            f"Context: {context}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_roles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_claude_roles.py studio/llm/claude_roles.py studio/llm/__init__.py
git commit -m "feat: add shared claude role payload parser"
```

### Task 2: Add Shared Claude Role Adapter Config and Invocation Tests

**Files:**
- Modify: `tests/test_claude_roles.py`
- Create: `studio/llm/claude_roles.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from studio.llm.claude_roles import ClaudeRoleAdapter, ClaudeRoleError, ReviewerPayload


def test_role_adapter_loads_existing_env_config(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "GAME_STUDIO_CLAUDE_ENABLED=true\n"
        "GAME_STUDIO_CLAUDE_MODE=text\n"
        "ANTHROPIC_API_KEY=test-key\n",
        encoding="utf-8",
    )

    adapter = ClaudeRoleAdapter(project_root=tmp_path)
    config = adapter.load_config()

    assert config.enabled is True
    assert config.mode == "text"
    assert config.api_key == "test-key"


def test_role_adapter_uses_subprocess_fallback_for_blocking_getcwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = ClaudeRoleAdapter(project_root=Path.cwd())

    async def _boom(role_name: str, context: dict[str, object], config: object):
        raise ClaudeRoleError("Failed to start Claude Code: Blocking call to os.getcwd")

    monkeypatch.setattr(adapter, "_generate_payload", _boom)
    monkeypatch.setattr(
        adapter,
        "_generate_payload_via_subprocess",
        lambda role_name, context: ReviewerPayload(
            decision="continue",
            reason="fallback subprocess succeeded",
            risks=[],
        ),
    )
    monkeypatch.setattr(
        adapter,
        "load_config",
        lambda: SimpleNamespace(
            enabled=True,
            mode="text",
            model=None,
            api_key="set",
            base_url=None,
        ),
    )

    payload = adapter.generate("reviewer", {"feature": "photo mode"})

    assert payload.reason == "fallback subprocess succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_roles.py -v`
Expected: FAIL because `ClaudeRoleAdapter` does not yet support config loading or subprocess fallback

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ClaudeRoleConfig:
    enabled: bool
    mode: str
    model: str | None
    api_key: str | None
    base_url: str | None


class ClaudeRoleAdapter:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = _repo_root_from(project_root)
        self._env_path = self.project_root / ".env"

    def load_config(self) -> ClaudeRoleConfig:
        values = _parse_dotenv(self._env_path)
        enabled = _parse_bool(values.get("GAME_STUDIO_CLAUDE_ENABLED"), default=False)
        mode = values.get("GAME_STUDIO_CLAUDE_MODE", "text").strip() or "text"
        if mode not in {"text", "tools_enabled"}:
            raise ClaudeRoleError(f"invalid_mode:{mode}")
        return ClaudeRoleConfig(
            enabled=enabled,
            mode=mode,
            model=values.get("GAME_STUDIO_CLAUDE_MODEL") or None,
            api_key=values.get("ANTHROPIC_API_KEY") or None,
            base_url=values.get("ANTHROPIC_BASE_URL") or None,
        )

    def generate(self, role_name: str, context: dict[str, object]) -> BaseModel:
        config = self.load_config()
        if not config.enabled:
            raise ClaudeRoleError("claude_disabled")
        if not config.api_key:
            raise ClaudeRoleError("missing_claude_configuration")
        try:
            return asyncio.run(self._generate_payload(role_name, context, config))
        except ClaudeRoleError as exc:
            if "Blocking call to os.getcwd" not in str(exc):
                raise
            return self._generate_payload_via_subprocess(role_name, context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_roles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_claude_roles.py studio/llm/claude_roles.py
git commit -m "feat: add shared claude role adapter"
```

### Task 3: Migrate Worker Adapter Compatibility onto Shared Role Infrastructure

**Files:**
- Modify: `tests/test_claude_worker.py`
- Modify: `studio/llm/claude_worker.py`
- Modify: `studio/llm/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.llm.claude_worker import ClaudeWorkerAdapter, ClaudeWorkerPayload


def test_worker_adapter_delegates_to_role_adapter(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRoleAdapter:
        def generate(self, role_name: str, context: dict[str, object]):
            calls.append((role_name, context))
            return ClaudeWorkerPayload(
                title="Lantern Vale",
                summary="Restore the valley.",
                genre="cozy strategy",
            )

    adapter = ClaudeWorkerAdapter(project_root=None, role_adapter=FakeRoleAdapter())
    payload = adapter.generate_design_brief("Design a simple 2D game concept")

    assert payload.title == "Lantern Vale"
    assert calls == [("worker", {"prompt": "Design a simple 2D game concept"})]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_worker.py::test_worker_adapter_delegates_to_role_adapter -v`
Expected: FAIL because `ClaudeWorkerAdapter` does not accept `role_adapter`

- [ ] **Step 3: Write minimal implementation**

```python
class ClaudeWorkerAdapter:
    def __init__(
        self,
        project_root: Path | None = None,
        role_adapter: ClaudeRoleAdapter | None = None,
    ) -> None:
        self.project_root = _repo_root_from(project_root)
        self._role_adapter = role_adapter or ClaudeRoleAdapter(project_root=self.project_root)

    def load_config(self) -> ClaudeRoleConfig:
        return self._role_adapter.load_config()

    def is_enabled(self) -> bool:
        return self.load_config().enabled

    def generate_design_brief(self, prompt: str) -> ClaudeWorkerPayload:
        payload = self._role_adapter.generate("worker", {"prompt": prompt})
        if not isinstance(payload, ClaudeWorkerPayload):
            raise ClaudeWorkerError("invalid_claude_output")
        return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_worker.py::test_worker_adapter_delegates_to_role_adapter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_claude_worker.py studio/llm/claude_worker.py studio/llm/__init__.py
git commit -m "refactor: route worker adapter through shared claude roles"
```

### Task 4: Add Reviewer Agent Claude Success and Fallback Tests

**Files:**
- Create: `tests/test_role_agents.py`
- Modify: `studio/agents/reviewer.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.reviewer import ReviewerAgent
from studio.llm.claude_roles import ClaudeRoleError, ReviewerPayload
from studio.schemas.runtime import RuntimeState


class FakeReviewerRunner:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def generate(self, role_name: str, context: dict[str, object]):
        if self.error is not None:
            raise self.error
        return self.payload


def _state() -> RuntimeState:
    return RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a simple 2D game concept"},
    )


def test_reviewer_uses_claude_payload_for_continue() -> None:
    agent = ReviewerAgent(
        claude_runner=FakeReviewerRunner(
            payload=ReviewerPayload(
                decision="continue",
                reason="title and summary are coherent",
                risks=["minor polish"],
            )
        )
    )

    result = agent.run(_state(), artifact_payload={"title": "Lantern Vale"})

    assert result.decision.value == "continue"
    assert result.trace["fallback_used"] is False
    assert result.state_patch["risks"] == ["minor polish"]


def test_reviewer_falls_back_on_claude_error() -> None:
    agent = ReviewerAgent(
        claude_runner=FakeReviewerRunner(error=ClaudeRoleError("boom"))
    )

    result = agent.run(_state(), artifact_payload={"title": "Lantern Vale"})

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_reviewer_uses_claude_payload_for_continue tests/test_role_agents.py::test_reviewer_falls_back_on_claude_error -v`
Expected: FAIL because `ReviewerAgent` does not accept `claude_runner` or emit fallback trace details

- [ ] **Step 3: Write minimal implementation**

```python
class ReviewerAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        artifact_payload = kwargs.get("artifact_payload", {})
        fallback = self._fallback_payload(artifact_payload)
        trace = {"node": "reviewer", "llm_provider": "claude", "fallback_used": True}
        try:
            payload = self._claude_runner.generate("reviewer", {"goal": state.goal, "artifact_payload": artifact_payload})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            payload = fallback
        else:
            trace["fallback_used"] = False

        decision = NodeDecision.CONTINUE if payload.decision == "continue" else NodeDecision.RETRY
        return NodeResult(
            decision=decision,
            state_patch={"plan": {"current_node": "reviewer"}, "risks": payload.risks},
            trace={**trace, "decision": decision.value, "reason": payload.reason},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_reviewer_uses_claude_payload_for_continue tests/test_role_agents.py::test_reviewer_falls_back_on_claude_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/reviewer.py
git commit -m "feat: back reviewer agent with claude adapter"
```

### Task 5: Add Design Agent Claude Success and Fallback Tests

**Files:**
- Modify: `tests/test_role_agents.py`
- Modify: `studio/agents/design.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.design import DesignAgent
from studio.llm.claude_roles import ClaudeRoleError, DesignPayload


def test_design_agent_uses_claude_payload() -> None:
    agent = DesignAgent(
        claude_runner=FakeReviewerRunner(
            payload=DesignPayload(
                title="Relic Design",
                summary="Adds relic progression.",
                core_rules=["one relic slot"],
                acceptance_criteria=["player can equip relics"],
                open_questions=["drop source"],
            )
        )
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is False
    assert result.trace["node"] == "design"
    assert result.state_patch["design_summary"] == "Adds relic progression."


def test_design_agent_falls_back_when_disabled() -> None:
    agent = DesignAgent(
        claude_runner=FakeReviewerRunner(error=ClaudeRoleError("claude_disabled"))
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_design_agent_uses_claude_payload tests/test_role_agents.py::test_design_agent_falls_back_when_disabled -v`
Expected: FAIL because `DesignAgent` is still a stub

- [ ] **Step 3: Write minimal implementation**

```python
class DesignAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace = {"node": "design", "llm_provider": "claude", "fallback_used": True}
        payload = self._fallback_payload(state)
        try:
            payload = self._claude_runner.generate("design", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
        else:
            trace["fallback_used"] = False
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "plan": {"current_node": "design"},
                "design_summary": payload.summary,
                "open_questions": payload.open_questions,
            },
            trace=trace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_design_agent_uses_claude_payload tests/test_role_agents.py::test_design_agent_falls_back_when_disabled -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/design.py
git commit -m "feat: back design agent with claude adapter"
```

### Task 6: Add Dev Agent Claude Success and Fallback Tests

**Files:**
- Modify: `tests/test_role_agents.py`
- Modify: `studio/agents/dev.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.dev import DevAgent
from studio.llm.claude_roles import ClaudeRoleError, DevPayload


def test_dev_agent_uses_claude_payload() -> None:
    agent = DevAgent(
        claude_runner=FakeReviewerRunner(
            payload=DevPayload(
                summary="Implemented relic progression.",
                changes=["added relic equip flow"],
                risks=["migration needed"],
                self_test_notes=["unit tests updated"],
            )
        )
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is False
    assert result.state_patch["implementation_summary"] == "Implemented relic progression."


def test_dev_agent_falls_back_on_invalid_output() -> None:
    agent = DevAgent(
        claude_runner=FakeReviewerRunner(error=ClaudeRoleError("invalid_claude_output"))
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "invalid_claude_output"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_dev_agent_uses_claude_payload tests/test_role_agents.py::test_dev_agent_falls_back_on_invalid_output -v`
Expected: FAIL because `DevAgent` is still a stub

- [ ] **Step 3: Write minimal implementation**

```python
class DevAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace = {"node": "dev", "llm_provider": "claude", "fallback_used": True}
        payload = self._fallback_payload()
        try:
            payload = self._claude_runner.generate("dev", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
        else:
            trace["fallback_used"] = False
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "implementation_summary": payload.summary,
                "risks": payload.risks,
                "self_test_notes": payload.self_test_notes,
            },
            trace=trace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_dev_agent_uses_claude_payload tests/test_role_agents.py::test_dev_agent_falls_back_on_invalid_output -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/dev.py
git commit -m "feat: back dev agent with claude adapter"
```

### Task 7: Add QA Agent Claude Success and Fallback Tests

**Files:**
- Modify: `tests/test_role_agents.py`
- Modify: `studio/agents/qa.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.qa import QaAgent
from studio.llm.claude_roles import ClaudeRoleError, QaPayload


def test_qa_agent_uses_claude_payload() -> None:
    agent = QaAgent(
        claude_runner=FakeReviewerRunner(
            payload=QaPayload(
                summary="Core flow verified.",
                passed=True,
                findings=[],
                suggested_bug=None,
            )
        )
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is False
    assert result.state_patch["qa_passed"] is True


def test_qa_agent_falls_back_on_error() -> None:
    agent = QaAgent(claude_runner=FakeReviewerRunner(error=ClaudeRoleError("boom")))

    result = agent.run(_state())

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_qa_agent_uses_claude_payload tests/test_role_agents.py::test_qa_agent_falls_back_on_error -v`
Expected: FAIL because `QaAgent` is still a stub

- [ ] **Step 3: Write minimal implementation**

```python
class QaAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace = {"node": "qa", "llm_provider": "claude", "fallback_used": True}
        payload = self._fallback_payload()
        try:
            payload = self._claude_runner.generate("qa", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
        else:
            trace["fallback_used"] = False
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "qa_summary": payload.summary,
                "qa_passed": payload.passed,
                "qa_findings": payload.findings,
            },
            trace=trace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_qa_agent_uses_claude_payload tests/test_role_agents.py::test_qa_agent_falls_back_on_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/qa.py
git commit -m "feat: back qa agent with claude adapter"
```

### Task 8: Add Quality Agent Claude Success and Fallback Tests

**Files:**
- Modify: `tests/test_role_agents.py`
- Modify: `studio/agents/quality.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.quality import QualityAgent
from studio.llm.claude_roles import ClaudeRoleError, QualityPayload


def test_quality_agent_uses_claude_payload() -> None:
    agent = QualityAgent(
        claude_runner=FakeReviewerRunner(
            payload=QualityPayload(
                summary="Ready for approval.",
                ready=True,
                risks=["monitor balance drift"],
                followups=["run smoke test"],
            )
        )
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is False
    assert result.state_patch["quality_ready"] is True


def test_quality_agent_falls_back_on_error() -> None:
    agent = QualityAgent(
        claude_runner=FakeReviewerRunner(error=ClaudeRoleError("claude_disabled"))
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_quality_agent_uses_claude_payload tests/test_role_agents.py::test_quality_agent_falls_back_on_error -v`
Expected: FAIL because `QualityAgent` is still a stub

- [ ] **Step 3: Write minimal implementation**

```python
class QualityAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace = {"node": "quality", "llm_provider": "claude", "fallback_used": True}
        payload = self._fallback_payload()
        try:
            payload = self._claude_runner.generate("quality", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
        else:
            trace["fallback_used"] = False
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "quality_summary": payload.summary,
                "quality_ready": payload.ready,
                "risks": payload.risks,
                "followups": payload.followups,
            },
            trace=trace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_quality_agent_uses_claude_payload tests/test_role_agents.py::test_quality_agent_falls_back_on_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/quality.py
git commit -m "feat: back quality agent with claude adapter"
```

### Task 9: Add Art Agent Claude Success and Fallback Tests

**Files:**
- Modify: `tests/test_role_agents.py`
- Modify: `studio/agents/art.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.agents.art import ArtAgent
from studio.llm.claude_roles import ArtPayload, ClaudeRoleError


def test_art_agent_uses_claude_payload() -> None:
    agent = ArtAgent(
        claude_runner=FakeReviewerRunner(
            payload=ArtPayload(
                summary="Warm diorama style.",
                style_direction="miniature watercolor",
                asset_list=["hero portrait", "relic icon set"],
            )
        )
    )

    result = agent.run(_state())

    assert result.trace["fallback_used"] is False
    assert result.state_patch["art_direction"] == "miniature watercolor"


def test_art_agent_falls_back_on_error() -> None:
    agent = ArtAgent(claude_runner=FakeReviewerRunner(error=ClaudeRoleError("boom")))

    result = agent.run(_state())

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_role_agents.py::test_art_agent_uses_claude_payload tests/test_role_agents.py::test_art_agent_falls_back_on_error -v`
Expected: FAIL because `ArtAgent` is still a stub

- [ ] **Step 3: Write minimal implementation**

```python
class ArtAgent:
    def __init__(self, claude_runner: ClaudeRoleAdapter | None = None, project_root: Path | None = None) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace = {"node": "art", "llm_provider": "claude", "fallback_used": True}
        payload = self._fallback_payload()
        try:
            payload = self._claude_runner.generate("art", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
        else:
            trace["fallback_used"] = False
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "art_summary": payload.summary,
                "art_direction": payload.style_direction,
                "asset_list": payload.asset_list,
            },
            trace=trace,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_role_agents.py::test_art_agent_uses_claude_payload tests/test_role_agents.py::test_art_agent_falls_back_on_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_role_agents.py studio/agents/art.py
git commit -m "feat: back art agent with claude adapter"
```

### Task 10: Add Full Role Model Coverage and Shared Prompt Contracts

**Files:**
- Modify: `tests/test_claude_roles.py`
- Modify: `studio/llm/claude_roles.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.llm.claude_roles import parse_role_payload


def test_parse_role_payload_validates_all_supported_roles() -> None:
    assert parse_role_payload(
        "worker",
        {"title": "Lantern Vale", "summary": "Restore the valley.", "genre": "cozy strategy"},
    ).genre == "cozy strategy"
    assert parse_role_payload(
        "design",
        {
            "title": "Relic Design",
            "summary": "Adds relic progression.",
            "core_rules": ["one relic slot"],
            "acceptance_criteria": ["player can equip relics"],
            "open_questions": ["drop source"],
        },
    ).title == "Relic Design"
    assert parse_role_payload(
        "dev",
        {
            "summary": "Implemented relic progression.",
            "changes": ["added equip flow"],
            "risks": ["migration needed"],
            "self_test_notes": ["tests updated"],
        },
    ).summary == "Implemented relic progression."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claude_roles.py::test_parse_role_payload_validates_all_supported_roles -v`
Expected: FAIL because not all role models are implemented

- [ ] **Step 3: Write minimal implementation**

```python
class ClaudeWorkerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str
    genre: str


class DesignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    summary: str
    core_rules: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class DevPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    self_test_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_claude_roles.py::test_parse_role_payload_validates_all_supported_roles -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_claude_roles.py studio/llm/claude_roles.py
git commit -m "feat: add full claude role payload coverage"
```

### Task 11: Update Graph and Dispatcher Compatibility Tests

**Files:**
- Modify: `tests/test_graph_run.py`
- Modify: `tests/test_agent_adapters.py`
- Modify: `studio/runtime/dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.runtime.dispatcher import RuntimeDispatcher


def test_dispatcher_still_lazy_loads_worker_agent() -> None:
    dispatcher = RuntimeDispatcher()

    worker = dispatcher.get("worker")
    reviewer = dispatcher.get("reviewer")

    assert worker.__class__.__name__ == "WorkerAgent"
    assert reviewer.__class__.__name__ == "ReviewerAgent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent_adapters.py::test_dispatcher_still_lazy_loads_worker_agent -v`
Expected: FAIL if the shared adapter refactor accidentally breaks import or initialization behavior

- [ ] **Step 3: Write minimal implementation**

```python
class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agent_specs = {
            "design": "studio.agents.design:DesignAgent",
            "dev": "studio.agents.dev:DevAgent",
            "qa": "studio.agents.qa:QaAgent",
            "quality": "studio.agents.quality:QualityAgent",
            "art": "studio.agents.art:ArtAgent",
            "planner": "studio.agents.planner:PlannerAgent",
            "worker": "studio.agents.worker:WorkerAgent",
            "reviewer": "studio.agents.reviewer:ReviewerAgent",
        }
        self._agents = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_agent_adapters.py::test_dispatcher_still_lazy_loads_worker_agent tests/test_graph_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_agent_adapters.py tests/test_graph_run.py studio/runtime/dispatcher.py
git commit -m "test: preserve dispatcher and graph compatibility"
```

### Task 12: Run Full Verification

**Files:**
- Modify: `tests/test_claude_worker.py`
- Modify: `tests/test_claude_roles.py`
- Modify: `tests/test_role_agents.py`
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/llm/claude_worker.py`
- Modify: `studio/agents/worker.py`
- Modify: `studio/agents/reviewer.py`
- Modify: `studio/agents/design.py`
- Modify: `studio/agents/dev.py`
- Modify: `studio/agents/qa.py`
- Modify: `studio/agents/quality.py`
- Modify: `studio/agents/art.py`

- [ ] **Step 1: Run targeted test groups**

```bash
uv run pytest tests/test_claude_roles.py tests/test_claude_worker.py tests/test_role_agents.py -v
```

Expected: PASS for all new shared-adapter and role-agent tests

- [ ] **Step 2: Run graph and adapter regression tests**

```bash
uv run pytest tests/test_graph_run.py tests/test_agent_adapters.py tests/test_langgraph_studio.py -v
```

Expected: PASS with unchanged graph and studio compatibility

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -q
```

Expected: all tests pass, no unexpected failures

- [ ] **Step 4: Review worktree state**

```bash
git status --short
```

Expected: only intended tracked file modifications and any known untracked local-only files

- [ ] **Step 5: Commit**

```bash
git add studio/llm/claude_roles.py studio/llm/__init__.py studio/llm/claude_worker.py studio/agents/worker.py studio/agents/reviewer.py studio/agents/design.py studio/agents/dev.py studio/agents/qa.py studio/agents/quality.py studio/agents/art.py tests/test_claude_roles.py tests/test_claude_worker.py tests/test_role_agents.py tests/test_graph_run.py tests/test_agent_adapters.py
git commit -m "feat: back workflow agents with claude sdk"
```
