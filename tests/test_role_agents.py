from __future__ import annotations

from studio.agents.dev import DevAgent
from studio.agents.design import DesignAgent
from studio.agents.art import ArtAgent
from studio.agents.quality import QualityAgent
from studio.agents.reviewer import ReviewerAgent
from studio.llm import (
    ArtPayload,
    ClaudeRoleError,
    DesignPayload,
    DevPayload,
    QaPayload,
    QualityPayload,
    ReviewerPayload,
)
from studio.runtime.graph import _merge_runtime_state
from studio.schemas.runtime import NodeDecision, RuntimeState


class FakeClaudeRunner:
    def __init__(
        self,
        *,
        expected_role_name: str,
        expected_context: dict[str, object],
        payload: ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload | None = None,
        error: Exception | None = None,
    ) -> None:
        self.expected_role_name = expected_role_name
        self.expected_context = expected_context
        self.payload = payload
        self.error = error

    def generate(
        self, role_name: str, context: dict[str, object]
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload:
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


def test_reviewer_uses_claude_payload_when_available() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="reviewer",
        expected_context={
            "artifact_payload": {
                "title": "Lantern Vale",
                "summary": "Restore the valley with patient strategy.",
            }
        },
        payload=ReviewerPayload(
            decision="continue",
            reason="The brief has a clear title and no blocking issues.",
            risks=["Clarify monetization scope."],
        )
    )

    result = ReviewerAgent(claude_runner=runner).run(
        _state(),
        artifact_payload={
            "title": "Lantern Vale",
            "summary": "Restore the valley with patient strategy.",
        },
    )

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["risks"] == ["Clarify monetization scope."]
    assert result.trace["fallback_used"] is False


def test_reviewer_falls_back_deterministically_when_claude_errors() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="reviewer",
        expected_context={
            "artifact_payload": {
                "title": "Lantern Vale",
                "summary": "Restore the valley with patient strategy.",
            }
        },
        error=ClaudeRoleError("boom"),
    )

    result = ReviewerAgent(claude_runner=runner).run(
        _state(),
        artifact_payload={
            "title": "Lantern Vale",
            "summary": "Restore the valley with patient strategy.",
        },
    )

    assert result.decision is NodeDecision.CONTINUE
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "boom"


def test_design_agent_uses_claude_payload_when_available() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="design",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=DesignPayload(
            title="Lantern Vale",
            summary="Restore the valley with patient strategy.",
            core_rules=["Guide villagers to relight shrines."],
            acceptance_criteria=["Players can complete a full restoration loop."],
            open_questions=["How many shrines should the first region contain?"],
        ),
    )

    result = DesignAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "design"
    design_brief = result.state_patch["telemetry"]["design_brief"]
    assert design_brief["title"] == "Lantern Vale"
    assert design_brief["summary"] == "Restore the valley with patient strategy."
    assert design_brief["core_rules"] == ["Guide villagers to relight shrines."]
    assert design_brief["acceptance_criteria"] == [
        "Players can complete a full restoration loop."
    ]
    assert design_brief["open_questions"] == [
        "How many shrines should the first region contain?"
    ]
    assert result.trace["fallback_used"] is False


def test_design_agent_falls_back_deterministically_when_claude_errors() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="design",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        error=ClaudeRoleError("claude_disabled"),
    )

    result = DesignAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "design"
    assert (
        result.state_patch["telemetry"]["design_brief"]["summary"]
        == "Design a simple 2D game concept"
    )
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_design_agent_patch_survives_runtime_state_merge_validation() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="design",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=DesignPayload(
            title="Lantern Vale",
            summary="Restore the valley with patient strategy.",
            core_rules=["Guide villagers to relight shrines."],
            acceptance_criteria=["Players can complete a full restoration loop."],
            open_questions=["How many shrines should the first region contain?"],
        ),
    )
    state = _state()

    result = DesignAgent(claude_runner=runner).run(state)
    merged = _merge_runtime_state(
        state,
        state_patch=result.state_patch,
        node_name="design",
        trace=result.trace,
    )

    assert merged.plan.current_node == "design"
    assert merged.telemetry["design_brief"] == {
        "title": "Lantern Vale",
        "summary": "Restore the valley with patient strategy.",
        "core_rules": ["Guide villagers to relight shrines."],
        "acceptance_criteria": ["Players can complete a full restoration loop."],
        "open_questions": ["How many shrines should the first region contain?"],
    }


def test_dev_agent_uses_claude_payload_when_available() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="dev",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=DevPayload(
            summary="Implemented the first playable loop.",
            changes=["Added movement controller.", "Connected shrine restore flow."],
            checks=["pytest tests/test_role_agents.py"],
            follow_ups=["Add combat tuning coverage."],
        ),
    )

    result = DevAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "dev"
    assert result.state_patch["telemetry"]["dev_report"] == {
        "summary": "Implemented the first playable loop.",
        "changes": ["Added movement controller.", "Connected shrine restore flow."],
        "checks": ["pytest tests/test_role_agents.py"],
        "follow_ups": ["Add combat tuning coverage."],
    }
    assert result.trace["fallback_used"] is False


def test_dev_agent_falls_back_deterministically_when_claude_errors() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="dev",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        error=ClaudeRoleError("claude_disabled"),
    )

    result = DevAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "dev"
    assert result.state_patch["telemetry"]["dev_report"] == {
        "summary": "Prepared a deterministic dev fallback report.",
        "changes": [],
        "checks": [],
        "follow_ups": [],
    }
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_dev_agent_patch_survives_runtime_state_merge_validation() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="dev",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=DevPayload(
            summary="Implemented the first playable loop.",
            changes=["Added movement controller."],
            checks=["pytest tests/test_role_agents.py"],
            follow_ups=["Add combat tuning coverage."],
        ),
    )
    state = _state()

    result = DevAgent(claude_runner=runner).run(state)
    merged = _merge_runtime_state(
        state,
        state_patch=result.state_patch,
        node_name="dev",
        trace=result.trace,
    )

    assert merged.plan.current_node == "dev"
    assert merged.telemetry["dev_report"] == {
        "summary": "Implemented the first playable loop.",
        "changes": ["Added movement controller."],
        "checks": ["pytest tests/test_role_agents.py"],
        "follow_ups": ["Add combat tuning coverage."],
    }


def test_qa_agent_uses_claude_payload_when_available() -> None:
    from studio.agents.qa import QaAgent

    runner = FakeClaudeRunner(
        expected_role_name="qa",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=QaPayload(
            summary="Validated the playable loop with a stable smoke pass.",
            passed=True,
            suggested_bug="Camera jitter appears after shrine completion.",
        ),
    )

    result = QaAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "qa"
    assert result.state_patch["telemetry"]["qa_report"] == {
        "summary": "Validated the playable loop with a stable smoke pass.",
        "passed": True,
        "suggested_bug": "Camera jitter appears after shrine completion.",
    }
    assert result.trace["fallback_used"] is False


def test_qa_agent_falls_back_deterministically_when_claude_errors() -> None:
    from studio.agents.qa import QaAgent

    runner = FakeClaudeRunner(
        expected_role_name="qa",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        error=ClaudeRoleError("claude_disabled"),
    )

    result = QaAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "qa"
    assert result.state_patch["telemetry"]["qa_report"] == {
        "summary": "Prepared a deterministic QA fallback report.",
        "passed": False,
        "suggested_bug": "QA fallback used because Claude output was unavailable.",
    }
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_qa_agent_patch_survives_runtime_state_merge_validation() -> None:
    from studio.agents.qa import QaAgent

    runner = FakeClaudeRunner(
        expected_role_name="qa",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=QaPayload(
            summary="Validated the playable loop with a stable smoke pass.",
            passed=True,
            suggested_bug="Camera jitter appears after shrine completion.",
        ),
    )
    state = _state()

    result = QaAgent(claude_runner=runner).run(state)
    merged = _merge_runtime_state(
        state,
        state_patch=result.state_patch,
        node_name="qa",
        trace=result.trace,
    )

    assert merged.plan.current_node == "qa"
    assert merged.telemetry["qa_report"] == {
        "summary": "Validated the playable loop with a stable smoke pass.",
        "passed": True,
        "suggested_bug": "Camera jitter appears after shrine completion.",
    }


def test_quality_agent_uses_claude_payload_when_available() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="quality",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=QualityPayload(
            summary="Ready for release candidate review.",
            ready=True,
            risks=["Economy balance still needs monitoring."],
            follow_ups=["Run a final controller smoke pass."],
        ),
    )

    result = QualityAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "quality"
    assert result.state_patch["telemetry"]["quality_report"] == {
        "summary": "Ready for release candidate review.",
        "ready": True,
        "risks": ["Economy balance still needs monitoring."],
        "follow_ups": ["Run a final controller smoke pass."],
    }
    assert result.trace["fallback_used"] is False


def test_quality_agent_falls_back_deterministically_when_claude_errors() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="quality",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        error=ClaudeRoleError("claude_disabled"),
    )

    result = QualityAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "quality"
    assert result.state_patch["telemetry"]["quality_report"] == {
        "summary": "Prepared a deterministic quality fallback report.",
        "ready": False,
        "risks": ["Claude quality report unavailable."],
        "follow_ups": [],
    }
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_quality_agent_patch_survives_runtime_state_merge_validation() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="quality",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=QualityPayload(
            summary="Ready for release candidate review.",
            ready=True,
            risks=["Economy balance still needs monitoring."],
            follow_ups=["Run a final controller smoke pass."],
        ),
    )
    state = _state()

    result = QualityAgent(claude_runner=runner).run(state)
    merged = _merge_runtime_state(
        state,
        state_patch=result.state_patch,
        node_name="quality",
        trace=result.trace,
    )

    assert merged.plan.current_node == "quality"
    assert merged.telemetry["quality_report"] == {
        "summary": "Ready for release candidate review.",
        "ready": True,
        "risks": ["Economy balance still needs monitoring."],
        "follow_ups": ["Run a final controller smoke pass."],
    }


def test_art_agent_uses_claude_payload_when_available() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="art",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=ArtPayload(
            summary="Defines a cozy painterly direction.",
            style_direction="storybook watercolor",
            asset_list=["hero portrait", "shrine icon", "village tileset"],
        ),
    )

    result = ArtAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "art"
    assert result.state_patch["telemetry"]["art_report"] == {
        "summary": "Defines a cozy painterly direction.",
        "style_direction": "storybook watercolor",
        "asset_list": ["hero portrait", "shrine icon", "village tileset"],
    }
    assert result.trace["fallback_used"] is False


def test_art_agent_falls_back_deterministically_when_claude_errors() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="art",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        error=ClaudeRoleError("claude_disabled"),
    )

    result = ArtAgent(claude_runner=runner).run(_state())

    assert result.decision is NodeDecision.CONTINUE
    assert result.state_patch["plan"]["current_node"] == "art"
    assert result.state_patch["telemetry"]["art_report"] == {
        "summary": "Prepared a deterministic art fallback report.",
        "style_direction": "clean placeholder concept art",
        "asset_list": [],
    }
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_art_agent_patch_survives_runtime_state_merge_validation() -> None:
    runner = FakeClaudeRunner(
        expected_role_name="art",
        expected_context={"goal": {"prompt": "Design a simple 2D game concept"}},
        payload=ArtPayload(
            summary="Defines a cozy painterly direction.",
            style_direction="storybook watercolor",
            asset_list=["hero portrait", "shrine icon", "village tileset"],
        ),
    )
    state = _state()

    result = ArtAgent(claude_runner=runner).run(state)
    merged = _merge_runtime_state(
        state,
        state_patch=result.state_patch,
        node_name="art",
        trace=result.trace,
    )

    assert merged.plan.current_node == "art"
    assert merged.telemetry["art_report"] == {
        "summary": "Defines a cozy painterly direction.",
        "style_direction": "storybook watercolor",
        "asset_list": ["hero portrait", "shrine icon", "village tileset"],
    }
