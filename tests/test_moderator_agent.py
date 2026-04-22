import pytest
from pathlib import Path

from studio.agents.moderator import ModeratorAgent
from studio.llm import ClaudeRoleError
from studio.llm.claude_roles import (
    ModeratorDiscussionPayload,
    ModeratorPreparePayload,
    ModeratorSummaryPayload,
)
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


class _StubClaudeRunner:
    def __init__(self, payloads=None, error_roles=None):
        self.payloads = payloads or {}
        self.error_roles = set(error_roles or [])
        self.calls = []

    def generate(self, role_name, context):
        self.calls.append((role_name, context))
        if role_name in self.error_roles:
            raise ClaudeRoleError(f"{role_name}_failed")
        return self.payloads[role_name]

    def consume_debug_record(self):
        return None


def test_discuss_returns_supplementary_and_unresolved_conflicts():
    runner = _StubClaudeRunner(
        payloads={
            "moderator_discussion": ModeratorDiscussionPayload(
                supplementary={"Scope vs timeline": "Lock scope for milestone one."},
                unresolved_conflicts=["Marketing beat timing still needs human approval."],
            )
        }
    )
    agent = ModeratorAgent(claude_runner=runner)

    result = agent.discuss(
        _state(),
        conflicts=["Scope vs timeline"],
        opinions={
            "design": {"summary": "Trim the milestone"},
            "dev": {"summary": "Protect the schedule"},
        },
        meeting_context={"agenda": ["Finalize release scope"]},
    )

    telemetry = result.state_patch.get("telemetry", {})
    assert telemetry["moderator_discussion"] == {
        "supplementary": {"Scope vs timeline": "Lock scope for milestone one."},
        "unresolved_conflicts": ["Marketing beat timing still needs human approval."],
    }
    assert result.trace["fallback_used"] is False
    assert runner.calls == [
        (
            "moderator_discussion",
            {
                "goal": _state().goal,
                "phase": "discussion",
                "conflicts": ["Scope vs timeline"],
                "opinions": {
                    "design": {"summary": "Trim the milestone"},
                    "dev": {"summary": "Protect the schedule"},
                },
                "meeting_context": {"agenda": ["Finalize release scope"]},
            },
        )
    ]


def test_prepare_and_summarize_forward_meeting_context_to_runner():
    runner = _StubClaudeRunner(
        payloads={
            "moderator_prepare": ModeratorPreparePayload(
                agenda=["Define the pitch"],
                attendees=["design", "dev"],
                focus_questions=["What is the first playable loop?"],
            ),
            "moderator_summary": ModeratorSummaryPayload(
                consensus_points=["Prototype in 2D first."],
                conflict_points=["Scope remains too broad."],
                conflict_resolution_needed=["Decide what ships in milestone one."],
            ),
        }
    )
    agent = ModeratorAgent(claude_runner=runner)
    state = _state(
        {
            "prompt": "Design a puzzle game",
            "requirement_id": "req_001",
            "meeting_context": {"prior_notes": ["Need a smaller milestone."]},
        }
    )

    prepare_result = agent.prepare(state)
    summarize_result = agent.summarize(
        state,
        opinions={"design": {"summary": "Keep it small"}},
        meeting_context={"agenda": ["Define the pitch"]},
    )

    assert prepare_result.trace["fallback_used"] is False
    assert summarize_result.trace["fallback_used"] is False
    assert runner.calls == [
        (
            "moderator_prepare",
            {
                "goal": state.goal,
                "phase": "prepare",
                "meeting_context": {"prior_notes": ["Need a smaller milestone."]},
            },
        ),
        (
            "moderator_summary",
            {
                "goal": state.goal,
                "phase": "summarize",
                "opinions": {"design": {"summary": "Keep it small"}},
                "meeting_context": {"agenda": ["Define the pitch"]},
            },
        ),
    ]


def test_discuss_falls_back_when_runner_raises_claude_role_error():
    runner = _StubClaudeRunner(error_roles={"moderator_discussion"})
    agent = ModeratorAgent(claude_runner=runner)

    result = agent.discuss(
        _state(),
        conflicts=["Scope vs timeline", "Launch platform"],
        opinions={"design": {"summary": "Cut scope"}},
        meeting_context={"agenda": ["Finalize release scope"]},
    )

    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "moderator_discussion_failed"
    assert result.state_patch["telemetry"]["moderator_discussion"] == {
        "supplementary": {
            "Scope vs timeline": "No automatic resolution available; user input is required.",
            "Launch platform": "No automatic resolution available; user input is required.",
        },
        "unresolved_conflicts": ["Scope vs timeline", "Launch platform"],
    }


def test_discuss_uses_meeting_context_from_state_goal_when_kwarg_is_missing():
    runner = _StubClaudeRunner(
        payloads={
            "moderator_discussion": ModeratorDiscussionPayload(
                supplementary={"Scope vs timeline": "Trim the first milestone."},
                unresolved_conflicts=["Launch platform still needs a decision."],
            )
        }
    )
    agent = ModeratorAgent(claude_runner=runner)
    state = _state(
        {
            "prompt": "Design a puzzle game",
            "requirement_id": "req_001",
            "meeting_context": {"agenda": ["Finalize release scope"]},
        }
    )

    result = agent.discuss(
        state,
        conflicts=["Scope vs timeline"],
        opinions={"design": {"summary": "Cut scope"}},
    )

    assert result.trace["fallback_used"] is False
    assert runner.calls == [
        (
            "moderator_discussion",
            {
                "goal": state.goal,
                "phase": "discussion",
                "conflicts": ["Scope vs timeline"],
                "opinions": {"design": {"summary": "Cut scope"}},
                "meeting_context": {"agenda": ["Finalize release scope"]},
            },
        )
    ]
