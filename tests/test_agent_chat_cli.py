from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app
from studio.agents.profile_schema import AgentProfileNotFoundError, AgentProfileValidationError
from studio.llm import ClaudeRoleError, ClaudeWorkerError


def test_agent_chat_single_turn_uses_profile_loader_and_role_adapter(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "qa"
            return FakeProfile()

    class FakePayload:
        summary = "QA completed"
        passed = True
        suggested_bug = None

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate(self, role_name: str, context: dict[str, object]) -> FakePayload:
            assert role_name == "qa"
            assert context == {"message": "Run smoke QA"}
            return FakePayload()

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 0
    assert '"summary": "QA completed"' in result.stdout
    assert '"passed": true' in result.stdout


def test_agent_chat_single_turn_supports_worker_adapter(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "Worker prompt."
        claude_project_root = Path("/repo/.claude/agents/worker")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "worker"
            return FakeProfile()

    class FakePayload:
        title = "Moonwell Garden"
        summary = "A cozy strategy loop."
        genre = "2d cozy strategy"

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate_design_brief(self, prompt: str) -> FakePayload:
            assert prompt == "Design a garden sim"
            return FakePayload()

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeWorkerAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "worker", "--message", "Design a garden sim"],
    )

    assert result.exit_code == 0
    assert '"title": "Moonwell Garden"' in result.stdout
    assert '"genre": "2d cozy strategy"' in result.stdout


def test_agent_chat_requires_message_without_interactive() -> None:
    result = CliRunner().invoke(app, ["agent", "chat", "--agent", "qa"])

    assert result.exit_code != 0
    assert "--message is required unless --interactive is set" in result.stderr


def test_agent_chat_interactive_reuses_adapter(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "qa"
            return FakeProfile()

    class FakePayload:
        def __init__(self, summary: str) -> None:
            self.summary = summary
            self.passed = True
            self.suggested_bug = None

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate(self, role_name: str, context: dict[str, object]) -> FakePayload:
            calls.append((role_name, context))
            return FakePayload(f"reply {len(calls)}")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--interactive"],
        input="first line\nsecond line\nquit\n",
    )

    assert result.exit_code == 0
    assert calls == [
        ("qa", {"message": "first line"}),
        ("qa", {"message": "second line"}),
    ]
    assert '"summary": "reply 1"' in result.stdout
    assert '"summary": "reply 2"' in result.stdout


def test_agent_chat_verbose_shows_profile_details(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "qa"
            return FakeProfile()

    class FakePayload:
        summary = "QA completed"
        passed = True
        suggested_bug = None

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate(self, role_name: str, context: dict[str, object]) -> FakePayload:
            assert role_name == "qa"
            assert context == {"message": "Run smoke QA"}
            return FakePayload()

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA", "--verbose"],
    )

    assert result.exit_code == 0
    assert '"agent": "qa"' in result.stdout
    assert '"profile_path":' in result.stdout
    assert f'"claude_project_root": {json.dumps(str(FakeProfile.claude_project_root))}' in result.stdout
    assert '"system_prompt": "QA prompt."' in result.stdout
    assert '"summary": "QA completed"' in result.stdout


def test_agent_chat_surfaces_role_adapter_errors_without_fallback(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "QA prompt."
        claude_project_root = Path("/repo/.claude/agents/qa")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "qa"
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate(self, role_name: str, context: dict[str, object]) -> object:
            raise ClaudeRoleError("adapter exploded")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 1
    assert "adapter exploded" in result.stderr


def test_agent_chat_surfaces_worker_adapter_errors_without_fallback(monkeypatch) -> None:
    class FakeProfile:
        system_prompt = "Worker prompt."
        claude_project_root = Path("/repo/.claude/agents/worker")

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> FakeProfile:
            assert agent_name == "worker"
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def generate_design_brief(self, prompt: str) -> object:
            raise ClaudeWorkerError("worker exploded")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeWorkerAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "worker", "--message", "Design a garden sim"],
    )

    assert result.exit_code == 1
    assert "worker exploded" in result.stderr


def test_agent_chat_surfaces_unknown_agent_name_from_loader(monkeypatch) -> None:
    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> object:
            raise AgentProfileNotFoundError(f"agent profile not found: {agent_name}")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "unknown", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 1
    assert "agent profile not found: unknown" in result.stderr


def test_agent_chat_surfaces_profile_loading_failures_from_loader(monkeypatch) -> None:
    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> object:
            raise AgentProfileValidationError("missing or invalid claude project root")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 1
    assert "missing or invalid claude project root" in result.stderr
