from pathlib import Path
from typing import Any

import pytest

from studio.runtime.graph import build_meeting_graph
from studio.schemas.requirement import RequirementCard
from studio.schemas.runtime import NodeDecision, NodeResult
from studio.storage.workspace import StudioWorkspace


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _meeting_node_result(telemetry: dict[str, object]) -> NodeResult:
    return NodeResult(
        decision=NodeDecision.CONTINUE,
        state_patch={"telemetry": telemetry},
        trace={"fallback_used": False},
    )


def _make_workspace(tmp_path: Path, *, title: str = "Design a puzzle game") -> Path:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title=title))
    return workspace_root


def _install_fake_participants(
    monkeypatch: pytest.MonkeyPatch,
    participant_cls: type,
) -> None:
    monkeypatch.setattr("studio.agents.design.DesignAgent", participant_cls)
    monkeypatch.setattr("studio.agents.art.ArtAgent", participant_cls)
    monkeypatch.setattr("studio.agents.dev.DevAgent", participant_cls)
    monkeypatch.setattr("studio.agents.qa.QaAgent", participant_cls)


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


def test_meeting_graph_uses_meeting_context_and_filters_unknown_attendees(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = _make_workspace(tmp_path)
    meeting_context = {
        "validated_attendees": ["design", "moderator", "design", "qa"],
        "source": "planner",
    }
    observed: dict[str, Any] = {
        "prepare_meeting_contexts": [],
        "participant_roles": [],
        "participant_contexts": [],
    }

    class FakeModeratorAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def prepare(
            self,
            state,
            *,
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            observed["prepare_meeting_contexts"].append(meeting_context)
            return _meeting_node_result(
                {
                    "moderator_prepare": {
                        "agenda": ["Discuss scope"],
                        "attendees": ["design", "moderator", "design", "qa"],
                        "focus_questions": [],
                    }
                }
            )

        def summarize(
            self,
            state,
            *,
            opinions: dict[str, dict[str, object]],
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_summary": {
                        "consensus_points": ["Consensus reached"],
                        "conflict_points": [],
                        "conflict_resolution_needed": False,
                    }
                }
            )

        def minutes(self, state, *, all_context: dict[str, object]) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_minutes": {
                        "title": "Meeting Notes",
                        "summary": "Summary",
                        "decisions": [],
                        "action_items": [],
                        "pending_user_decisions": [],
                    }
                }
            )

    class FakeParticipantAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def run(self, state) -> NodeResult:
            role = str(state.goal["role"])
            observed["participant_roles"].append(role)
            observed["participant_contexts"].append(state.goal.get("meeting_context"))
            return _meeting_node_result(
                {
                    f"{role}_report": {
                        "summary": f"{role} summary",
                        "proposals": [f"{role} proposal"],
                        "risks": [],
                        "open_questions": [],
                    }
                }
            )

    monkeypatch.setattr("studio.agents.moderator.ModeratorAgent", FakeModeratorAgent)
    _install_fake_participants(monkeypatch, FakeParticipantAgent)

    graph = build_meeting_graph()
    result = graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Design a puzzle game",
            "meeting_context": meeting_context,
        }
    )

    assert observed["prepare_meeting_contexts"] == [meeting_context]
    assert observed["participant_roles"] == ["design", "qa"]
    assert observed["participant_contexts"] == [meeting_context, meeting_context]
    assert result["minutes"]["attendees"] == ["design", "qa"]
    assert [opinion["agent_role"] for opinion in result["minutes"]["opinions"]] == [
        "design",
        "qa",
    ]


def test_meeting_graph_defaults_attendees_when_validation_removes_everything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = _make_workspace(tmp_path)
    observed_roles: list[str] = []

    class FakeModeratorAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def prepare(
            self,
            state,
            *,
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_prepare": {
                        "agenda": ["Discuss scope"],
                        "attendees": ["moderator", "producer", "moderator"],
                        "focus_questions": [],
                    }
                }
            )

        def summarize(
            self,
            state,
            *,
            opinions: dict[str, dict[str, object]],
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_summary": {
                        "consensus_points": [],
                        "conflict_points": [],
                        "conflict_resolution_needed": False,
                    }
                }
            )

        def minutes(self, state, *, all_context: dict[str, object]) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_minutes": {
                        "title": "Meeting Notes",
                        "summary": "Summary",
                        "decisions": [],
                        "action_items": [],
                        "pending_user_decisions": [],
                    }
                }
            )

    class FakeParticipantAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def run(self, state) -> NodeResult:
            role = str(state.goal["role"])
            observed_roles.append(role)
            return _meeting_node_result(
                {
                    f"{role}_report": {
                        "summary": f"{role} summary",
                        "proposals": [f"{role} proposal"],
                        "risks": [],
                        "open_questions": [],
                    }
                }
            )

    monkeypatch.setattr("studio.agents.moderator.ModeratorAgent", FakeModeratorAgent)
    _install_fake_participants(monkeypatch, FakeParticipantAgent)

    graph = build_meeting_graph()
    result = graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Design a puzzle game",
            "meeting_context": {"validated_attendees": []},
        }
    )

    assert observed_roles == ["design", "dev", "qa"]
    assert result["minutes"]["attendees"] == ["design", "dev", "qa"]
    assert [opinion["agent_role"] for opinion in result["minutes"]["opinions"]] == [
        "design",
        "dev",
        "qa",
    ]


def test_meeting_graph_runs_single_conflict_discussion_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = _make_workspace(tmp_path)
    discussion_calls: list[dict[str, object]] = []

    class FakeModeratorAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def prepare(
            self,
            state,
            *,
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_prepare": {
                        "agenda": ["Discuss scope"],
                        "attendees": ["design"],
                        "focus_questions": [],
                    }
                }
            )

        def summarize(
            self,
            state,
            *,
            opinions: dict[str, dict[str, object]],
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            needs_conflict_round = state.goal["prompt"] == "Needs conflict discussion"
            return _meeting_node_result(
                {
                    "moderator_summary": {
                        "consensus_points": ["Keep puzzle loop"],
                        "conflict_points": ["Resolve progression scope"] if needs_conflict_round else [],
                        "conflict_resolution_needed": needs_conflict_round,
                    }
                }
            )

        def discuss(
            self,
            state,
            *,
            conflicts: list[str],
            opinions: dict[str, dict[str, object]],
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            discussion_calls.append(
                {
                    "conflicts": conflicts,
                    "opinions": opinions,
                    "meeting_context": meeting_context,
                }
            )
            return _meeting_node_result(
                {
                    "moderator_discussion": {
                        "supplementary": {
                            "Resolve progression scope": "Need player-facing priority call."
                        },
                        "unresolved_conflicts": ["Resolve progression scope"],
                    }
                }
            )

        def minutes(self, state, *, all_context: dict[str, object]) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_minutes": {
                        "title": "Meeting Notes",
                        "summary": "Summary",
                        "decisions": [],
                        "action_items": [],
                        "pending_user_decisions": list(
                            all_context.get("unresolved_conflicts", [])
                        ),
                    }
                }
            )

    class FakeParticipantAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def run(self, state) -> NodeResult:
            role = str(state.goal["role"])
            return _meeting_node_result(
                {
                    f"{role}_report": {
                        "summary": f"{role} summary",
                        "proposals": [f"{role} proposal"],
                        "risks": [],
                        "open_questions": [],
                    }
                }
            )

    monkeypatch.setattr("studio.agents.moderator.ModeratorAgent", FakeModeratorAgent)
    _install_fake_participants(monkeypatch, FakeParticipantAgent)

    graph = build_meeting_graph()

    conflict_result = graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Needs conflict discussion",
            "meeting_context": {"validated_attendees": ["design"]},
        }
    )

    no_conflict_result = graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "No conflict discussion needed",
            "meeting_context": {"validated_attendees": ["design"]},
        }
    )

    assert discussion_calls == [
        {
            "conflicts": ["Resolve progression scope"],
            "opinions": {
                "design": {
                    "agent_role": "design",
                    "summary": "design summary",
                    "proposals": ["design proposal"],
                    "risks": [],
                    "open_questions": [],
                }
            },
            "meeting_context": {"validated_attendees": ["design"]},
        }
    ]
    assert conflict_result["minutes"]["supplementary"][
        "Resolve progression scope"
    ] == "Need player-facing priority call."
    assert conflict_result["minutes"]["pending_user_decisions"] == [
        "Resolve progression scope"
    ]
    assert "Resolve progression scope" not in no_conflict_result["minutes"][
        "supplementary"
    ]


def test_meeting_graph_compatibility_mode_warns_when_meeting_context_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = _make_workspace(tmp_path)

    class FakeModeratorAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def prepare(
            self,
            state,
            *,
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_prepare": {
                        "agenda": ["Discuss scope"],
                        "attendees": ["design", "dev", "qa"],
                        "focus_questions": [],
                    }
                }
            )

        def summarize(
            self,
            state,
            *,
            opinions: dict[str, dict[str, object]],
            meeting_context: dict[str, object] | None = None,
        ) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_summary": {
                        "consensus_points": ["Consensus reached"],
                        "conflict_points": [],
                        "conflict_resolution_needed": False,
                    }
                }
            )

        def minutes(self, state, *, all_context: dict[str, object]) -> NodeResult:
            return _meeting_node_result(
                {
                    "moderator_minutes": {
                        "title": "Meeting Notes",
                        "summary": "Summary",
                        "decisions": [],
                        "action_items": [],
                        "pending_user_decisions": [],
                    }
                }
            )

    class FakeParticipantAgent:
        def __init__(self, project_root: Path | None = None) -> None:
            self.project_root = project_root

        def run(self, state) -> NodeResult:
            role = str(state.goal["role"])
            return _meeting_node_result(
                {
                    f"{role}_report": {
                        "summary": f"{role} summary",
                        "proposals": [f"{role} proposal"],
                        "risks": [],
                        "open_questions": [],
                    }
                }
            )

    monkeypatch.setattr("studio.agents.moderator.ModeratorAgent", FakeModeratorAgent)
    _install_fake_participants(monkeypatch, FakeParticipantAgent)

    graph = build_meeting_graph()
    result = graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Design a puzzle game",
        }
    )

    warning = result["minutes"]["supplementary"].get("compatibility_warning", "")
    assert "meeting_context" in warning
