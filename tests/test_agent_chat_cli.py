from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app
from studio.agents.profile_schema import AgentProfileNotFoundError, AgentProfileValidationError
from studio.llm import ClaudeRoleError, ClaudeWorkerError


def test_agent_chat_single_turn_uses_profile_loader_and_raw_chat(monkeypatch) -> None:
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

        def chat(self, message: str) -> str:
            assert message == "Run smoke QA"
            return "QA completed"

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 0
    assert "QA completed" in result.stdout


def test_agent_chat_single_turn_supports_worker_profile(monkeypatch) -> None:
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

        def chat(self, message: str) -> str:
            assert message == "Design a garden sim"
            return "Moonwell Garden\nA cozy strategy loop."

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "worker", "--message", "Design a garden sim"],
    )

    assert result.exit_code == 0
    assert "Moonwell Garden" in result.stdout


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

    calls: list[str] = []

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def chat(self, message: str) -> str:
            calls.append(message)
            return f"reply {len(calls)}"

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--interactive"],
        input="first line\nsecond line\nquit\n",
    )

    assert result.exit_code == 0
    assert calls == ["first line", "second line"]
    assert "reply 1" in result.stdout
    assert "reply 2" in result.stdout


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

    class FakeRunner:
        def __init__(self, project_root: Path | None = None, profile: object | None = None) -> None:
            assert project_root is None
            assert profile is not None

        def chat(self, message: str) -> str:
            assert message == "Run smoke QA"
            return "QA completed"

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
    assert "QA completed" in result.stdout


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

        def chat(self, message: str) -> str:
            raise ClaudeRoleError("adapter exploded")

    monkeypatch.setattr("studio.interfaces.cli.AgentProfileLoader", FakeLoader)
    monkeypatch.setattr("studio.interfaces.cli.ClaudeRoleAdapter", FakeRunner)

    result = CliRunner().invoke(
        app,
        ["agent", "chat", "--agent", "qa", "--message", "Run smoke QA"],
    )

    assert result.exit_code == 1
    assert "adapter exploded" in result.stderr


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
