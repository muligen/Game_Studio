# Agent Profile Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict per-agent checked-in profiles, remove runtime prompt/config fallback behavior, and expose a CLI to chat directly with any configured agent.

**Architecture:** Introduce a small profile subsystem in `studio/agents/` that loads and validates one YAML file per agent, then pass those typed profiles into the Claude adapters so prompt text and Claude SDK working directory come only from the profile. Add a dedicated `agent chat` CLI command that uses the same loader and adapters so workflow execution and debugging share the same configuration path.

**Tech Stack:** Python 3.12, Pydantic, PyYAML, Typer, pytest, Claude Agent SDK

---

## File Structure

### New files

- `studio/agents/profile_schema.py`
  Defines configuration error types and the `AgentProfile` model.
- `studio/agents/profile_loader.py`
  Loads `studio/agents/profiles/<agent>.yaml`, resolves relative paths, and validates the target Claude directory.
- `studio/agents/profiles/worker.yaml`
- `studio/agents/profiles/reviewer.yaml`
- `studio/agents/profiles/design.yaml`
- `studio/agents/profiles/dev.yaml`
- `studio/agents/profiles/qa.yaml`
- `studio/agents/profiles/quality.yaml`
- `studio/agents/profiles/art.yaml`
  Checked-in default profiles for every managed agent.
- `.claude/agents/worker/CLAUDE.md`
- `.claude/agents/reviewer/CLAUDE.md`
- `.claude/agents/design/CLAUDE.md`
- `.claude/agents/dev/CLAUDE.md`
- `.claude/agents/qa/CLAUDE.md`
- `.claude/agents/quality/CLAUDE.md`
- `.claude/agents/art/CLAUDE.md`
  Minimal checked-in Claude context directories so strict path validation passes.
- `tests/test_agent_profiles.py`
  Focused tests for loader and schema validation.
- `tests/test_agent_chat_cli.py`
  CLI tests for single-turn, interactive, and verbose behavior.

### Modified files

- `studio/agents/__init__.py`
  Re-export profile types and loader helpers if needed by tests and CLI.
- `studio/agents/worker.py`
- `studio/agents/reviewer.py`
- `studio/agents/design.py`
- `studio/agents/dev.py`
- `studio/agents/qa.py`
- `studio/agents/quality.py`
- `studio/agents/art.py`
  Load agent profiles and pass them into adapters.
- `studio/llm/claude_roles.py`
  Accept `AgentProfile`, remove prompt fallback logic, and run Claude SDK under the profile root.
- `studio/llm/claude_worker.py`
  Same as above for worker mode and worker subprocess path.
- `studio/llm/__init__.py`
  Export any new profile-aware adapter types if tests import them from the package root.
- `studio/interfaces/cli.py`
  Add `agent` Typer namespace and `chat` command.
- `tests/test_claude_roles.py`
- `tests/test_claude_worker.py`
- `tests/test_role_agents.py`
  Update adapter and agent tests to reflect profile-driven configuration.

## Task 1: Add Strict Agent Profile Schema and Loader

**Files:**
- Create: `studio/agents/profile_schema.py`
- Create: `studio/agents/profile_loader.py`
- Create: `tests/test_agent_profiles.py`
- Modify: `studio/agents/__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from studio.agents.profile_loader import AgentProfileLoader
from studio.agents.profile_schema import (
    AgentProfileNotFoundError,
    AgentProfileValidationError,
)


def test_loader_reads_valid_profile(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "studio" / "agents" / "profiles"
    claude_root = tmp_path / ".claude" / "agents" / "qa"
    claude_root.mkdir(parents=True)
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "qa.yaml").write_text(
        "\n".join(
            [
                "name: qa",
                "system_prompt: |",
                "  You are the qa role.",
                "claude_project_root: .claude/agents/qa",
            ]
        ),
        encoding="utf-8",
    )

    profile = AgentProfileLoader(repo_root=tmp_path).load("qa")

    assert profile.name == "qa"
    assert profile.system_prompt == "You are the qa role."
    assert profile.claude_project_root == claude_root.resolve()


def test_loader_rejects_missing_profile(tmp_path: Path) -> None:
    with pytest.raises(AgentProfileNotFoundError, match="agent profile not found: qa"):
        AgentProfileLoader(repo_root=tmp_path).load("qa")


def test_loader_rejects_missing_system_prompt(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "studio" / "agents" / "profiles"
    claude_root = tmp_path / ".claude" / "agents" / "qa"
    claude_root.mkdir(parents=True)
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "qa.yaml").write_text(
        "\n".join(
            [
                "name: qa",
                "claude_project_root: .claude/agents/qa",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        AgentProfileValidationError,
        match="agent profile 'qa' missing required field: system_prompt",
    ):
        AgentProfileLoader(repo_root=tmp_path).load("qa")


def test_loader_rejects_missing_claude_directory(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "studio" / "agents" / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "qa.yaml").write_text(
        "\n".join(
            [
                "name: qa",
                "system_prompt: |",
                "  You are the qa role.",
                "claude_project_root: .claude/agents/qa",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        AgentProfileValidationError,
        match="agent profile 'qa' claude_project_root does not exist:",
    ):
        AgentProfileLoader(repo_root=tmp_path).load("qa")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agent_profiles.py`
Expected: FAIL with `ModuleNotFoundError` for `studio.agents.profile_loader` or missing symbols.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/agents/profile_schema.py
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AgentProfileError(RuntimeError):
    pass


class AgentProfileNotFoundError(AgentProfileError):
    pass


class AgentProfileValidationError(AgentProfileError):
    pass


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    claude_project_root: Path
    enabled: bool = True
    model: str | None = None
    fallback_policy: str | None = None
```

```python
# studio/agents/profile_loader.py
from __future__ import annotations

from pathlib import Path

import yaml

from studio.agents.profile_schema import (
    AgentProfile,
    AgentProfileNotFoundError,
    AgentProfileValidationError,
)


class AgentProfileLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.profiles_root = self.repo_root / "studio" / "agents" / "profiles"

    def load(self, agent_name: str) -> AgentProfile:
        path = self.profiles_root / f"{agent_name}.yaml"
        if not path.exists():
            raise AgentProfileNotFoundError(f"agent profile not found: {agent_name}")

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise AgentProfileValidationError(f"agent profile '{agent_name}' is not a mapping")

        for field_name in ("name", "system_prompt", "claude_project_root"):
            value = raw.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise AgentProfileValidationError(
                    f"agent profile '{agent_name}' missing required field: {field_name}"
                )

        if raw["name"] != agent_name:
            raise AgentProfileValidationError(
                f"agent profile '{agent_name}' name mismatch: {raw['name']}"
            )

        claude_root = Path(raw["claude_project_root"])
        if not claude_root.is_absolute():
            claude_root = (self.repo_root / claude_root).resolve()

        if not claude_root.exists() or not claude_root.is_dir():
            raise AgentProfileValidationError(
                f"agent profile '{agent_name}' claude_project_root does not exist: {claude_root}"
            )

        return AgentProfile(
            name=raw["name"],
            system_prompt=raw["system_prompt"].strip(),
            claude_project_root=claude_root,
            enabled=bool(raw.get("enabled", True)),
            model=raw.get("model"),
            fallback_policy=raw.get("fallback_policy"),
        )
```

```python
# studio/agents/__init__.py
from .profile_loader import AgentProfileLoader
from .profile_schema import (
    AgentProfile,
    AgentProfileError,
    AgentProfileNotFoundError,
    AgentProfileValidationError,
)

__all__ = [
    "AgentProfile",
    "AgentProfileError",
    "AgentProfileLoader",
    "AgentProfileNotFoundError",
    "AgentProfileValidationError",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_agent_profiles.py`
Expected: PASS with `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add studio/agents/profile_schema.py studio/agents/profile_loader.py studio/agents/__init__.py tests/test_agent_profiles.py
git commit -m "feat: add strict agent profile loader"
```

## Task 2: Check In Default Agent Profiles and Claude Context Roots

**Files:**
- Create: `studio/agents/profiles/worker.yaml`
- Create: `studio/agents/profiles/reviewer.yaml`
- Create: `studio/agents/profiles/design.yaml`
- Create: `studio/agents/profiles/dev.yaml`
- Create: `studio/agents/profiles/qa.yaml`
- Create: `studio/agents/profiles/quality.yaml`
- Create: `studio/agents/profiles/art.yaml`
- Create: `.claude/agents/worker/CLAUDE.md`
- Create: `.claude/agents/reviewer/CLAUDE.md`
- Create: `.claude/agents/design/CLAUDE.md`
- Create: `.claude/agents/dev/CLAUDE.md`
- Create: `.claude/agents/qa/CLAUDE.md`
- Create: `.claude/agents/quality/CLAUDE.md`
- Create: `.claude/agents/art/CLAUDE.md`
- Test: `tests/test_agent_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader


def test_repository_contains_profiles_for_all_managed_agents() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    loader = AgentProfileLoader(repo_root=repo_root)

    for agent_name in ("worker", "reviewer", "design", "dev", "qa", "quality", "art"):
        profile = loader.load(agent_name)
        assert profile.name == agent_name
        assert profile.system_prompt
        assert profile.claude_project_root.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agent_profiles.py::test_repository_contains_profiles_for_all_managed_agents`
Expected: FAIL with `agent profile not found` for the first missing checked-in profile.

- [ ] **Step 3: Write minimal implementation**

```yaml
# studio/agents/profiles/reviewer.yaml
name: reviewer
enabled: true
system_prompt: |
  You are the reviewer role.
  Return only JSON with decision, reason, and risks.
  decision must be continue or stop.
  reason must explain the choice.
  risks must be a list of concrete issues.
claude_project_root: .claude/agents/reviewer
model: ""
fallback_policy: deterministic
```

```yaml
# studio/agents/profiles/worker.yaml
name: worker
enabled: true
system_prompt: |
  You are generating a compact game design brief.
  Return only an object with the keys title, summary, and genre.
  Do not add markdown fences, explanations, or extra keys.
claude_project_root: .claude/agents/worker
model: ""
fallback_policy: deterministic
```

```markdown
# .claude/agents/reviewer/CLAUDE.md
# Reviewer Agent Context

This Claude project root belongs only to the reviewer agent.
Use the repository-managed system prompt and honor the required JSON output contract.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_agent_profiles.py`
Expected: PASS with the repository-backed profile test included.

- [ ] **Step 5: Commit**

```bash
git add studio/agents/profiles .claude/agents tests/test_agent_profiles.py
git commit -m "feat: add checked-in agent profiles"
```

## Task 3: Make Claude Adapters Profile-Driven and Remove Prompt Fallbacks

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/llm/claude_worker.py`
- Modify: `studio/llm/__init__.py`
- Test: `tests/test_claude_roles.py`
- Test: `tests/test_claude_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from studio.agents.profile_schema import AgentProfile
from studio.llm.claude_roles import ClaudeRoleAdapter
from studio.llm.claude_worker import ClaudeWorkerAdapter


def test_role_adapter_builds_prompt_from_profile() -> None:
    profile = AgentProfile(
        name="qa",
        system_prompt="QA profile prompt.",
        claude_project_root=Path("/tmp/qa"),
    )

    prompt = ClaudeRoleAdapter(profile=profile).debug_prompt("qa", {"goal": {"prompt": "Check feature"}})

    assert prompt.startswith("QA profile prompt.")
    assert "Context:" in prompt


def test_worker_adapter_builds_prompt_from_profile() -> None:
    profile = AgentProfile(
        name="worker",
        system_prompt="Worker profile prompt.",
        claude_project_root=Path("/tmp/worker"),
    )

    prompt = ClaudeWorkerAdapter(profile=profile).debug_prompt("Design a simple 2D game concept")

    assert prompt.startswith("Worker profile prompt.")
    assert "User prompt:" in prompt
```

```python
def test_role_adapter_uses_profile_claude_root(monkeypatch, tmp_path) -> None:
    profile = AgentProfile(
        name="reviewer",
        system_prompt="Reviewer prompt.",
        claude_project_root=tmp_path / ".claude" / "agents" / "reviewer",
    )
    profile.claude_project_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(profile=profile, project_root=tmp_path)
    calls = {}

    class FakeOptions:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("studio.llm.claude_roles.ClaudeAgentOptions", FakeOptions)

    # invoke the async method with a fake query path in the real test file
    assert calls["cwd"] == profile.claude_project_root
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_claude_roles.py tests/test_claude_worker.py`
Expected: FAIL because adapters do not accept `profile=` and still rely on hardcoded prompt maps.

- [ ] **Step 3: Write minimal implementation**

```python
# claude_roles.py constructor and prompt source
class ClaudeRoleAdapter:
    def __init__(self, profile: AgentProfile, project_root: Path | None = None) -> None:
        self.profile = profile
        self.project_root = _repo_root_from(project_root)
        self._env_path = self.project_root / ".env"
        self._last_debug_record: dict[str, object] | None = None

    def debug_prompt(self, role_name: str, context: dict[str, object]) -> str:
        _require_active_role(role_name)
        return self._prompt(context)

    def _prompt(self, context: dict[str, object]) -> str:
        payload = json.dumps(context, ensure_ascii=False, sort_keys=True)
        return f"{self.profile.system_prompt.rstrip()}\nContext: {payload}"
```

```python
# claude_roles.py SDK options
options = ClaudeAgentOptions(
    cwd=self.profile.claude_project_root,
    model=config.model or self.profile.model,
    tools=[] if config.mode == "text" else None,
    permission_mode="default",
    setting_sources=["project"],
    env=self._sdk_env(config),
    output_format=self._output_format(role_name),
)
```

```python
# claude_worker.py prompt source
class ClaudeWorkerAdapter:
    def __init__(self, profile: AgentProfile, project_root: Path | None = None, role_adapter: Any | None = None) -> None:
        self.profile = profile
        self.project_root = _repo_root_from(project_root)
        self._env_path = self.project_root / ".env"
        self._role_adapter = role_adapter
        self._last_debug_record: dict[str, object] | None = None

    def _prompt(self, user_prompt: str) -> str:
        return (
            f"{self.profile.system_prompt.rstrip()}\n"
            f"User prompt: {user_prompt}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_claude_roles.py tests/test_claude_worker.py`
Expected: PASS with updated profile-driven prompt assertions.

- [ ] **Step 5: Commit**

```bash
git add studio/llm/claude_roles.py studio/llm/claude_worker.py studio/llm/__init__.py tests/test_claude_roles.py tests/test_claude_worker.py
git commit -m "refactor: drive Claude adapters from agent profiles"
```

## Task 4: Wire Managed Agents to Load Their Own Profiles

**Files:**
- Modify: `studio/agents/worker.py`
- Modify: `studio/agents/reviewer.py`
- Modify: `studio/agents/design.py`
- Modify: `studio/agents/dev.py`
- Modify: `studio/agents/qa.py`
- Modify: `studio/agents/quality.py`
- Modify: `studio/agents/art.py`
- Test: `tests/test_role_agents.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from studio.agents import AgentProfile
from studio.agents.design import DesignAgent


def test_design_agent_loads_profile_by_default(monkeypatch, tmp_path: Path) -> None:
    profile = AgentProfile(
        name="design",
        system_prompt="Design profile prompt.",
        claude_project_root=tmp_path / ".claude" / "agents" / "design",
    )
    profile.claude_project_root.mkdir(parents=True)
    calls = []

    class FakeLoader:
        def load(self, agent_name: str) -> AgentProfile:
            calls.append(agent_name)
            return profile

    monkeypatch.setattr("studio.agents.design.AgentProfileLoader", lambda repo_root=None: FakeLoader())

    agent = DesignAgent(project_root=tmp_path)

    assert calls == ["design"]
    assert agent._claude_runner.profile == profile
```

```python
def test_review_agent_bubbles_profile_errors(monkeypatch, tmp_path: Path) -> None:
    from studio.agents.profile_schema import AgentProfileValidationError
    from studio.agents.reviewer import ReviewerAgent

    class FakeLoader:
        def load(self, agent_name: str):
            raise AgentProfileValidationError("agent profile 'reviewer' missing required field: system_prompt")

    monkeypatch.setattr("studio.agents.reviewer.AgentProfileLoader", lambda repo_root=None: FakeLoader())

    with pytest.raises(AgentProfileValidationError, match="missing required field: system_prompt"):
        ReviewerAgent(project_root=tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_role_agents.py`
Expected: FAIL because agents do not construct a loader or profile-aware adapter yet.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/agents/design.py pattern to repeat across managed agents
from studio.agents import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError


class DesignAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        loader = AgentProfileLoader(repo_root=project_root)
        profile = loader.load("design")
        self._claude_runner = ClaudeRoleAdapter(profile=profile, project_root=project_root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_role_agents.py`
Expected: PASS and existing fake-runner tests remain green.

- [ ] **Step 5: Commit**

```bash
git add studio/agents/worker.py studio/agents/reviewer.py studio/agents/design.py studio/agents/dev.py studio/agents/qa.py studio/agents/quality.py studio/agents/art.py tests/test_role_agents.py
git commit -m "feat: load managed agents from checked-in profiles"
```

## Task 5: Add `agent chat` CLI for Single-Turn and Interactive Debugging

**Files:**
- Modify: `studio/interfaces/cli.py`
- Create: `tests/test_agent_chat_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app


def test_agent_chat_single_turn_prints_reply(monkeypatch, tmp_path: Path) -> None:
    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, role_name: str, context: dict[str, object]):
            class Payload:
                summary = "Looks good"
                passed = True
                suggested_bug = None
            return Payload()

    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)
    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", lambda repo_root=None: type("FakeLoader", (), {"load": lambda self, name: object()})())

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Smoke test the shrine loop"],
    )

    assert result.exit_code == 0
    assert "Looks good" in result.stdout


def test_agent_chat_requires_message_without_interactive() -> None:
    result = CliRunner().invoke(app, ["agent", "chat", "--agent", "qa"])

    assert result.exit_code != 0
    assert "--message is required unless --interactive is set" in result.stdout


def test_agent_chat_verbose_shows_profile_details(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, role_name: str, context: dict[str, object]):
            class Payload:
                summary = "QA completed"
                passed = True
                suggested_bug = None
            return Payload()

    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)
    monkeypatch.setattr(
        "studio.interfaces.cli.AgentProfileLoader",
        lambda repo_root=None: type("FakeLoader", (), {"load": lambda self, name: FakeProfile()})(),
    )

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA", "--verbose"],
    )

    assert result.exit_code == 0
    assert '"agent": "qa"' in result.stdout
    assert '"claude_project_root": "/repo/.claude/agents/qa"' in result.stdout
    assert "QA completed" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agent_chat_cli.py`
Expected: FAIL because the `agent` Typer namespace and `chat` command do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/interfaces/cli.py
agent_app = typer.Typer(help="Direct agent debugging commands.")
app.add_typer(agent_app, name="agent")


def _agent_reply_to_text(agent_name: str, payload: object) -> str:
    if hasattr(payload, "model_dump_json") and callable(payload.model_dump_json):
        return payload.model_dump_json(indent=2)
    if hasattr(payload, "model_dump") and callable(payload.model_dump):
        return json.dumps(payload.model_dump(), indent=2, ensure_ascii=False)
    if hasattr(payload, "__dict__"):
        return json.dumps(payload.__dict__, indent=2, ensure_ascii=False, default=str)
    return str(payload)


@agent_app.command("chat")
def agent_chat(
    agent: str = typer.Option(..., "--agent"),
    message: str | None = typer.Option(None, "--message"),
    interactive: bool = typer.Option(False, "--interactive"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    if not interactive and not message:
        _fail_cli("--message is required unless --interactive is set")

    loader = AgentProfileLoader()
    profile = loader.load(agent)

    if agent == "worker":
        runner = ClaudeWorkerAdapter(profile=profile)
        if interactive:
            while True:
                user_input = typer.prompt(f"{agent}>")
                if user_input.strip().lower() in {"exit", "quit"}:
                    break
                payload = runner.generate_design_brief(user_input)
                typer.echo(_agent_reply_to_text(agent, payload))
            return
        payload = runner.generate_design_brief(message or "")
    else:
        runner = ClaudeRoleAdapter(profile=profile)
        context = {"message": message} if not interactive else {}
        if interactive:
            while True:
                user_input = typer.prompt(f"{agent}>")
                if user_input.strip().lower() in {"exit", "quit"}:
                    break
                payload = runner.generate(agent, {"message": user_input})
                typer.echo(_agent_reply_to_text(agent, payload))
            return
        payload = runner.generate(agent, context)

    if verbose:
        typer.echo(json.dumps({
            "agent": agent,
            "profile_path": str((Path(__file__).resolve().parents[1] / "agents" / "profiles" / f"{agent}.yaml").resolve()),
            "claude_project_root": str(profile.claude_project_root),
            "system_prompt": profile.system_prompt,
        }, indent=2, ensure_ascii=False))
    typer.echo(_agent_reply_to_text(agent, payload))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_agent_chat_cli.py tests/test_cli.py`
Expected: PASS with new CLI coverage and no regression to existing commands.

- [ ] **Step 5: Commit**

```bash
git add studio/interfaces/cli.py tests/test_agent_chat_cli.py
git commit -m "feat: add direct CLI chat for managed agents"
```

## Task 6: Run Full Regression Sweep and Remove Leftover Hardcoded Prompt Usage

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/llm/claude_worker.py`
- Test: `tests/test_agent_profiles.py`
- Test: `tests/test_agent_chat_cli.py`
- Test: `tests/test_claude_roles.py`
- Test: `tests/test_claude_worker.py`
- Test: `tests/test_role_agents.py`
- Test: `tests/test_graph_run.py`
- Test: `tests/test_langgraph_studio.py`

- [ ] **Step 1: Write the failing test**

```python
from studio.llm import claude_roles as claude_roles_module


def test_role_runtime_no_longer_uses_hardcoded_prompt_map(monkeypatch, tmp_path) -> None:
    profile = AgentProfile(
        name="reviewer",
        system_prompt="Profile-owned reviewer prompt.",
        claude_project_root=tmp_path / ".claude" / "agents" / "reviewer",
    )
    profile.claude_project_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(profile=profile, project_root=tmp_path)

    monkeypatch.setattr(claude_roles_module, "_ROLE_PROMPTS", {"reviewer": "OLD PROMPT"})

    prompt = adapter.debug_prompt("reviewer", {"feature": "photo mode"})

    assert prompt.startswith("Profile-owned reviewer prompt.")
    assert "OLD PROMPT" not in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_claude_roles.py::test_role_runtime_no_longer_uses_hardcoded_prompt_map`
Expected: FAIL if any runtime prompt path still reads `_ROLE_PROMPTS`.

- [ ] **Step 3: Write minimal implementation**

```python
# claude_roles.py
_ROLE_PROMPTS: dict[str, str] = {}


def _prompt(self, context: dict[str, object]) -> str:
    payload = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return f"{self.profile.system_prompt.rstrip()}\nContext: {payload}"
```

```python
# claude_worker.py
def _prompt(self, user_prompt: str) -> str:
    return f"{self.profile.system_prompt.rstrip()}\nUser prompt: {user_prompt}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_agent_profiles.py tests/test_agent_chat_cli.py tests/test_claude_roles.py tests/test_claude_worker.py tests/test_role_agents.py tests/test_graph_run.py tests/test_langgraph_studio.py`
Expected: PASS with all targeted tests green.

- [ ] **Step 5: Commit**

```bash
git add studio/llm/claude_roles.py studio/llm/claude_worker.py tests/test_agent_profiles.py tests/test_agent_chat_cli.py tests/test_claude_roles.py tests/test_claude_worker.py tests/test_role_agents.py tests/test_graph_run.py tests/test_langgraph_studio.py
git commit -m "test: verify strict profile-driven agent runtime"
```
