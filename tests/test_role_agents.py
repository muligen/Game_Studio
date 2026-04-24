from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from studio.agents import AgentProfile
from studio.agents.art import ArtAgent
from studio.agents.dev import DevAgent
from studio.agents.design import DesignAgent
from studio.agents.moderator import ModeratorAgent
from studio.agents.qa import QaAgent
from studio.agents.quality import QualityAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent
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


def _profile(agent_name: str, tmp_path: Path) -> AgentProfile:
    claude_project_root = tmp_path / ".claude" / "agents" / agent_name
    claude_project_root.mkdir(parents=True)
    return AgentProfile(
        name=agent_name,
        system_prompt=f"{agent_name} profile prompt",
        claude_project_root=claude_project_root,
    )


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


@pytest.mark.parametrize(
    ("module_name", "class_name", "agent_name"),
    [
        ("studio.agents.worker", "WorkerAgent", "worker"),
    ],
)
def test_worker_agent_loads_profile_from_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module_name: str,
    class_name: str,
    agent_name: str,
) -> None:
    module = importlib.import_module(module_name)
    agent_cls = getattr(module, class_name)
    profile = _profile(agent_name, tmp_path)
    calls: list[tuple[Path | None, str]] = []

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            calls.append((repo_root, "__init__"))

        def load(self, requested_agent_name: str) -> AgentProfile:
            init_repo_root, _ = calls.pop()
            calls.append((init_repo_root, requested_agent_name))
            return profile

    monkeypatch.setattr(module, "AgentProfileLoader", FakeLoader)

    agent = agent_cls(project_root=tmp_path)

    assert calls == [(tmp_path, agent_name)]
    assert agent._claude_runner.profile == profile


@pytest.mark.parametrize(
    ("module_name", "class_name", "agent_name"),
    [
        ("studio.agents.reviewer", "ReviewerAgent", "reviewer"),
        ("studio.agents.design", "DesignAgent", "design"),
        ("studio.agents.dev", "DevAgent", "dev"),
        ("studio.agents.qa", "QaAgent", "qa"),
        ("studio.agents.quality", "QualityAgent", "quality"),
        ("studio.agents.art", "ArtAgent", "art"),
        ("studio.agents.moderator", "ModeratorAgent", "moderator"),
    ],
)
def test_meeting_graph_agents_load_profiles_from_repository_root_and_preserve_workspace_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module_name: str,
    class_name: str,
    agent_name: str,
) -> None:
    module = importlib.import_module(module_name)
    agent_cls = getattr(module, class_name)
    profile = _profile(agent_name, tmp_path)
    loader_calls: list[tuple[Path | None, str]] = []
    adapter_calls: list[tuple[Path | None, AgentProfile]] = []

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            loader_calls.append((repo_root, "__init__"))

        def load(self, requested_agent_name: str) -> AgentProfile:
            init_repo_root, _ = loader_calls.pop()
            loader_calls.append((init_repo_root, requested_agent_name))
            return profile

    class FakeAdapter:
        def __init__(self, project_root: Path | None = None, profile: AgentProfile | None = None, **_: object) -> None:
            assert profile is not None
            adapter_calls.append((project_root, profile))
            self.profile = profile

    monkeypatch.setattr(module, "AgentProfileLoader", FakeLoader)
    monkeypatch.setattr(module, "ClaudeRoleAdapter", FakeAdapter)

    agent = agent_cls(project_root=tmp_path)

    assert loader_calls == [(None, agent_name)]
    assert adapter_calls == [(tmp_path, profile)]
    assert agent._claude_runner.profile == profile


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("studio.agents.worker", "WorkerAgent"),
        ("studio.agents.reviewer", "ReviewerAgent"),
        ("studio.agents.design", "DesignAgent"),
        ("studio.agents.dev", "DevAgent"),
        ("studio.agents.qa", "QaAgent"),
        ("studio.agents.quality", "QualityAgent"),
        ("studio.agents.art", "ArtAgent"),
        ("studio.agents.moderator", "ModeratorAgent"),
    ],
)
def test_managed_agents_preserve_injected_claude_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module_name: str,
    class_name: str,
) -> None:
    module = importlib.import_module(module_name)
    agent_cls = getattr(module, class_name)

    class UnexpectedLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            raise AssertionError("loader should not be constructed when claude_runner is injected")

    monkeypatch.setattr(module, "AgentProfileLoader", UnexpectedLoader)

    runner = object()
    agent = agent_cls(claude_runner=runner, project_root=tmp_path)

    assert agent._claude_runner is runner


def test_reviewer_agent_bubbles_profile_loader_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from studio.agents.profile_schema import AgentProfileValidationError

    class FakeLoader:
        def __init__(self, repo_root: Path | None = None) -> None:
            assert repo_root is None

        def load(self, agent_name: str) -> AgentProfile:
            raise AgentProfileValidationError(
                "agent profile 'reviewer' missing required field: system_prompt"
            )

    monkeypatch.setattr("studio.agents.reviewer.AgentProfileLoader", FakeLoader)

    with pytest.raises(
        AgentProfileValidationError,
        match="missing required field: system_prompt",
    ):
        ReviewerAgent(project_root=tmp_path)


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
    assert "llm_prompt" not in result.trace
    assert "llm_context" not in result.trace


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
    assert "llm_prompt" not in result.trace


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
    assert "llm_prompt" not in result.trace
    assert "llm_context" not in result.trace


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
    assert "llm_prompt" not in result.trace
    assert "llm_context" not in result.trace


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
    assert "llm_prompt" not in result.trace
    assert "llm_context" not in result.trace


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
