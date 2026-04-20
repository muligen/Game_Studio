import pytest
from pathlib import Path
from unittest.mock import MagicMock
from studio.agents.moderator import ModeratorAgent
from studio.schemas.runtime import RuntimeState


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _state(goal=None):
    return RuntimeState(
        project_id="meeting-project",
        run_id="run-001",
        task_id="task-001",
        goal=goal or {"prompt": "Design a puzzle game", "requirement_id": "req_001"},
    )


def test_prepare_returns_agenda_and_attendees():
    agent = ModeratorAgent(project_root=_REPO_ROOT)
    result = agent.prepare(_state())
    assert result.decision.value == "continue"
    telemetry = result.state_patch.get("telemetry", {})
    prep = telemetry.get("moderator_prepare", {})
    assert "agenda" in prep
    assert "attendees" in prep
    assert isinstance(prep["agenda"], list)
    assert isinstance(prep["attendees"], list)


def test_summarize_returns_consensus_and_conflicts():
    agent = ModeratorAgent(project_root=_REPO_ROOT)
    opinions = {
        "design": {"summary": "good", "proposals": ["x"], "risks": [], "open_questions": []},
        "dev": {"summary": "hard", "proposals": ["y"], "risks": ["perf"], "open_questions": []},
    }
    result = agent.summarize(_state(), opinions=opinions)
    telemetry = result.state_patch.get("telemetry", {})
    summary = telemetry.get("moderator_summary", {})
    assert "consensus_points" in summary
    assert "conflict_points" in summary


def test_minutes_produces_final_output():
    agent = ModeratorAgent(project_root=_REPO_ROOT)
    context = {
        "agenda": ["Game scope"],
        "opinions": {"design": {"summary": "ok"}},
        "consensus_points": ["Use 2D"],
        "conflict_points": ["Timeline tight"],
    }
    result = agent.minutes(_state(), all_context=context)
    telemetry = result.state_patch.get("telemetry", {})
    minutes = telemetry.get("moderator_minutes", {})
    assert "title" in minutes
    assert "pending_user_decisions" in minutes
