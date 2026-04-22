from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app
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
        def __init__(self, repo_root=None):
            pass

        def load(self, agent_name: str):
            return FakeProfile()

    class FakeRunner:
        def __init__(self, project_root=None, profile=None, session_id=None, resume_session=False):
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
        def __init__(self, project_root=None, profile=None, session_id=None, resume_session=False):
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
        def __init__(self, project_root=None, profile=None, session_id=None, resume_session=False):
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


def test_project_kickoff_creates_sessions_and_runs_meeting(monkeypatch, tmp_path: Path) -> None:
    from studio.storage.workspace import StudioWorkspace
    from studio.schemas.requirement import RequirementCard

    workspace = tmp_path / ".studio-data"
    ws = StudioWorkspace(workspace)
    ws.ensure_layout()
    ws.requirements.save(RequirementCard(id="req_001", title="Design a card game"))

    meeting_result = {
        "node_name": "moderator_minutes",
        "minutes": {
            "id": "meeting_001",
            "requirement_id": "req_001",
            "title": "Kickoff",
        },
    }
    captured_state: dict[str, object] = {}

    class FakeGraph:
        def invoke(self, state):
            captured_state.update(state)
            return {**state, **meeting_result}

    monkeypatch.setattr("studio.interfaces.cli.build_meeting_graph", lambda: FakeGraph())

    result = CliRunner().invoke(
        app,
        ["project", "kickoff", "--workspace", str(tmp_path),
         "--requirement-id", "req_001", "--user-intent", "Design a card game"],
    )

    assert result.exit_code == 0
    parts = result.stdout.strip().split()
    assert parts[0].startswith("proj_")
    assert "kickoff_complete" in result.stdout

    reg = SessionRegistry(workspace)
    for agent in ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]:
        assert reg.find(parts[0], agent) is not None, f"missing {agent}"
    assert Path(str(captured_state["project_root"])).resolve() == Path(__file__).resolve().parents[1]


def test_project_kickoff_fails_without_workspace() -> None:
    result = CliRunner().invoke(app, ["project", "kickoff"])
    assert result.exit_code != 0
