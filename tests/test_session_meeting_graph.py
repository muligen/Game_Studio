from __future__ import annotations

from pathlib import Path

import pytest

from studio.runtime.graph import build_meeting_graph
from studio.schemas.requirement import RequirementCard
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
        "project_root": str(_REPO_ROOT),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
    })

    assert result["node_name"] == "moderator_minutes"
    assert "minutes" in result


def test_meeting_graph_with_project_id_looks_up_sessions(tmp_path: Path):
    workspace, workspace_root = _setup_workspace(tmp_path)

    registry = SessionRegistry(Path(workspace_root))
    registry.create("proj_1", "req_001", "moderator", "mod-session-123")
    registry.create("proj_1", "req_001", "design", "design-session-456")
    registry.create("proj_1", "req_001", "dev", "dev-session-789")
    registry.create("proj_1", "req_001", "qa", "qa-session-012")

    captured_session_ids: list[str | None] = []

    import studio.llm.claude_roles as cr_module
    original_init = cr_module.ClaudeRoleAdapter.__init__

    def tracking_init(self, **kwargs):
        captured_session_ids.append(kwargs.get("session_id"))
        return original_init(self, **kwargs)

    import unittest.mock
    with unittest.mock.patch.object(cr_module.ClaudeRoleAdapter, "__init__", tracking_init):
        graph = build_meeting_graph()
        result = graph.invoke({
            "workspace_root": workspace_root,
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Design a puzzle game",
            "project_id": "proj_1",
        })

    assert result["node_name"] == "moderator_minutes"
    non_none = [s for s in captured_session_ids if s is not None]
    assert len(non_none) > 0


def test_meeting_graph_with_project_id_missing_session_still_completes(tmp_path: Path):
    workspace, workspace_root = _setup_workspace(tmp_path)

    # Only create moderator session, not agent sessions
    registry = SessionRegistry(Path(workspace_root))
    registry.create("proj_1", "req_001", "moderator", "mod-session-123")

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": workspace_root,
        "project_root": str(_REPO_ROOT),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
        "project_id": "proj_1",
    })

    assert result["node_name"] == "moderator_minutes"
