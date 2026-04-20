import pytest
from pathlib import Path
from studio.runtime.graph import build_meeting_graph
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _disable_live_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "studio.llm.claude_worker.ClaudeWorkerAdapter.load_config",
        lambda self: type(
            "Config",
            (),
            {
                "enabled": False,
                "mode": "text",
                "model": None,
                "api_key": None,
                "base_url": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "studio.llm.claude_roles.ClaudeRoleAdapter.load_config",
        lambda self: type(
            "Config",
            (),
            {
                "enabled": False,
                "mode": "text",
                "model": None,
                "api_key": None,
                "base_url": None,
            },
        )(),
    )


def test_meeting_graph_runs_to_completion(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Design a puzzle game"))

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(_REPO_ROOT),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
    })

    assert result["node_name"] == "moderator_minutes"
    assert "minutes" in result
    minutes = result["minutes"]
    assert minutes["requirement_id"] == "req_001"
    assert isinstance(minutes["opinions"], list)
    assert isinstance(minutes["consensus_points"], list)
    assert isinstance(minutes["pending_user_decisions"], list)


def test_meeting_graph_rejects_missing_inputs() -> None:
    graph = build_meeting_graph()
    with pytest.raises(ValueError, match="workspace_root is required"):
        graph.invoke({"requirement_id": "req_001", "user_intent": "test"})


def test_meeting_graph_saves_minutes_to_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Card battler"))

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(_REPO_ROOT),
        "requirement_id": "req_001",
        "user_intent": "Card battler",
    })

    # Check minutes are in result
    assert result["minutes"]["requirement_id"] == "req_001"
    assert result["minutes"]["id"] == "meeting_001"
