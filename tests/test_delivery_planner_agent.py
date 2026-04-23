from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from studio.agents.delivery_planner import DeliveryPlannerAgent
from studio.agents.profile_loader import load_agent_profile
from studio.llm import ClaudeRoleError, DeliveryPlannerPayload
from studio.schemas.runtime import NodeDecision, RuntimeState


def _valid_payload_dict() -> dict[str, object]:
    return {
        "tasks": [
            {
                "title": "Design core loop",
                "description": "Create the main gameplay loop",
                "owner_agent": "design",
                "depends_on": [],
                "acceptance_criteria": ["Loop is documented"],
                "source_evidence": ["meeting minutes section 1"],
            },
        ],
        "decision_gate": {
            "items": [
                {
                    "question": "Which art style?",
                    "context": "Two options were proposed",
                    "options": ["pixel art", "watercolor"],
                    "source_evidence": ["art opinion"],
                },
            ],
        },
    }


def test_delivery_planner_payload_parses_valid_json() -> None:
    payload = DeliveryPlannerPayload.model_validate(_valid_payload_dict())

    assert len(payload.tasks) == 1
    assert payload.tasks[0].title == "Design core loop"
    assert payload.tasks[0].owner_agent == "design"
    assert payload.tasks[0].depends_on == []
    assert len(payload.decision_gate.items) == 1
    assert payload.decision_gate.items[0].question == "Which art style?"
    assert payload.decision_gate.items[0].options == ["pixel art", "watercolor"]


def test_delivery_planner_payload_rejects_extra_fields() -> None:
    data = _valid_payload_dict()
    data["unexpected_field"] = "nope"  # type: ignore[typeddict-unknown-key]

    with pytest.raises(ValidationError):
        DeliveryPlannerPayload.model_validate(data)


def test_delivery_planner_profile_loads_correctly() -> None:
    profile = load_agent_profile("delivery_planner")

    assert profile.name == "delivery_planner"
    assert profile.system_prompt.strip()
    assert "delivery planner" in profile.system_prompt.lower()


def test_claude_md_exists_and_contains_agent_name() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    claude_md = repo_root / ".claude" / "agents" / "delivery_planner" / "CLAUDE.md"

    assert claude_md.is_file(), "CLAUDE.md missing for delivery_planner"
    text = claude_md.read_text(encoding="utf-8")
    assert "delivery_planner" in text


class FakeClaudeRunner:
    def __init__(
        self,
        *,
        expected_role_name: str,
        expected_context: dict[str, object],
        payload: DeliveryPlannerPayload | None = None,
        error: Exception | None = None,
    ) -> None:
        self.expected_role_name = expected_role_name
        self.expected_context = expected_context
        self.payload = payload
        self.error = error

    def generate(
        self, role_name: str, context: dict[str, object]
    ) -> DeliveryPlannerPayload:
        assert role_name == self.expected_role_name
        assert context == self.expected_context
        if self.error is not None:
            raise self.error
        if self.payload is None:
            raise AssertionError("payload must be provided for successful fake runs")
        return self.payload


def _state() -> RuntimeState:
    return RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a simple 2D game concept"},
    )


def test_delivery_planner_agent_returns_correct_node_result_with_payload() -> None:
    payload = DeliveryPlannerPayload.model_validate(_valid_payload_dict())
    runner = FakeClaudeRunner(
        expected_role_name="delivery_planner",
        expected_context={
            "goal": {"prompt": "Design a simple 2D game concept"},
            "phase": "plan_generation",
        },
        payload=payload,
    )

    result = DeliveryPlannerAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "delivery_planner"
    delivery_plan = result.state_patch["telemetry"]["delivery_plan"]
    assert len(delivery_plan["tasks"]) == 1
    assert delivery_plan["tasks"][0]["title"] == "Design core loop"
    assert delivery_plan["decision_gate"]["items"][0]["question"] == "Which art style?"
    assert result.trace["fallback_used"] is False


def test_delivery_planner_agent_falls_back_on_error() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="delivery_planner",
        expected_context={
            "goal": {"prompt": "Design a simple 2D game concept"},
            "phase": "plan_generation",
        },
        error=ClaudeRoleError("claude_disabled"),
    )

    result = DeliveryPlannerAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "delivery_planner"
    assert result.state_patch["telemetry"]["delivery_plan"] == {
        "tasks": [],
        "decision_gate": {"items": []},
    }
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"
