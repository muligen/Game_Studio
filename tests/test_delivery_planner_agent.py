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


def _state() -> RuntimeState:
    return RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a simple 2D game concept"},
    )


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


def test_delivery_planner_payload_parses_valid_json() -> None:
    payload = DeliveryPlannerPayload.model_validate(_valid_payload_dict())

    assert len(payload.tasks) == 1
    assert payload.tasks[0].title == "Design core loop"
    assert payload.tasks[0].owner_agent == "design"
    assert payload.tasks[0].depends_on == []
    assert len(payload.decision_gate.items) == 1
    assert payload.decision_gate.items[0].question == "Which art style?"


def test_delivery_planner_payload_accepts_owner_agent_aliases() -> None:
    data = _valid_payload_dict()
    data["tasks"][0]["owner_agent"] = "moderator"  # type: ignore[index]

    payload = DeliveryPlannerPayload.model_validate(data)

    assert payload.tasks[0].owner_agent == "moderator"


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
    assert result.trace["fallback_used"] is False


def test_delivery_planner_agent_generate_payload_returns_serializable_dict() -> None:
    payload = DeliveryPlannerPayload.model_validate(_valid_payload_dict())
    runner = FakeClaudeRunner(
        expected_role_name="delivery_planner",
        expected_context={"meeting_id": "meet_001"},
        payload=payload,
    )

    result = DeliveryPlannerAgent(claude_runner=runner).generate_payload({"meeting_id": "meet_001"})

    assert result["tasks"][0]["title"] == "Design core loop"
    assert result["decision_gate"]["items"][0]["question"] == "Which art style?"


def test_delivery_planner_agent_raises_on_error() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="delivery_planner",
        expected_context={
            "goal": {"prompt": "Design a simple 2D game concept"},
            "phase": "plan_generation",
        },
        error=ClaudeRoleError("claude_disabled"),
    )

    with pytest.raises(ClaudeRoleError, match="claude_disabled"):
        DeliveryPlannerAgent(claude_runner=runner).run(_state())


def test_delivery_planner_agent_loads_profile_from_repo_root_and_preserves_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    sentinel_profile = object()
    observed: dict[str, object] = {}

    def fake_load(self: object, agent_name: str) -> object:
        observed["loader_repo_root"] = getattr(self, "repo_root")
        observed["agent_name"] = agent_name
        return sentinel_profile

    class FakeAdapter:
        def __init__(
            self,
            *,
            project_root: Path | None = None,
            profile: object | None = None,
            session_id: str | None = None,
            resume_session: bool = False,
        ) -> None:
            observed["adapter_project_root"] = project_root
            observed["adapter_profile"] = profile
            observed["adapter_session_id"] = session_id
            observed["adapter_resume_session"] = resume_session

    monkeypatch.setattr("studio.agents.delivery_planner.AgentProfileLoader.load", fake_load)
    monkeypatch.setattr("studio.agents.delivery_planner.ClaudeRoleAdapter", FakeAdapter)

    DeliveryPlannerAgent(project_root=project_root)

    assert observed["agent_name"] == "delivery_planner"
    assert observed["loader_repo_root"] == repo_root
    assert observed["adapter_project_root"] == project_root
    assert observed["adapter_profile"] is sentinel_profile
