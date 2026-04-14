from __future__ import annotations

from pathlib import Path

import pytest

from studio.agents.worker import WorkerAgent
from studio.llm.claude_worker import (
    ClaudeWorkerAdapter,
    ClaudeWorkerError,
    ClaudeWorkerPayload,
)
from studio.schemas.runtime import RuntimeState


class FakeClaudeRunner:
    def __init__(
        self,
        *,
        enabled: bool = True,
        payload: ClaudeWorkerPayload | None = None,
        error: Exception | None = None,
    ) -> None:
        self.enabled = enabled
        self.payload = payload
        self.error = error

    def is_enabled(self) -> bool:
        return self.enabled

    def generate_design_brief(self, prompt: str) -> ClaudeWorkerPayload:
        if self.error is not None:
            raise self.error
        if self.payload is None:
            raise AssertionError("payload must be provided for successful fake runs")
        return self.payload


def _state(prompt: object = "Design a simple 2D game concept") -> RuntimeState:
    return RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": prompt},
    )


def test_worker_uses_claude_payload_when_enabled() -> None:
    runner = FakeClaudeRunner(
        payload=ClaudeWorkerPayload(
            title="Lantern Vale",
            summary="A calm strategy game about restoring glowing ruins.",
            genre="2d cozy strategy",
        )
    )
    result = WorkerAgent(claude_runner=runner).run(_state())

    assert result.artifacts[0].payload["title"] == "Lantern Vale"
    assert result.trace["llm_provider"] == "claude"
    assert result.trace["fallback_used"] is False


def test_worker_falls_back_when_claude_disabled() -> None:
    result = WorkerAgent(claude_runner=FakeClaudeRunner(enabled=False)).run(_state())

    assert result.artifacts[0].payload["title"] == "Moonwell Garden"
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"


def test_worker_falls_back_when_claude_runner_errors() -> None:
    result = WorkerAgent(
        claude_runner=FakeClaudeRunner(error=ClaudeWorkerError("boom"))
    ).run(_state())

    assert result.artifacts[0].payload["title"] == "Moonwell Garden"
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "boom"


def test_worker_rejects_non_string_prompt() -> None:
    with pytest.raises(TypeError, match="goal.prompt must be a string"):
        WorkerAgent(claude_runner=FakeClaudeRunner(enabled=False)).run(_state(prompt=123))


def test_worker_falls_back_when_env_config_is_incomplete(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("GAME_STUDIO_CLAUDE_ENABLED=true\n", encoding="utf-8")

    result = WorkerAgent(project_root=tmp_path).run(_state())

    assert result.artifacts[0].payload["title"] == "Moonwell Garden"
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "missing_claude_configuration"


def test_worker_falls_back_when_env_config_is_invalid(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GAME_STUDIO_CLAUDE_ENABLED=true\nGAME_STUDIO_CLAUDE_MODE=broken\n",
        encoding="utf-8",
    )

    result = WorkerAgent(project_root=tmp_path).run(_state())

    assert result.artifacts[0].payload["title"] == "Moonwell Garden"
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "invalid_mode:broken"


def test_adapter_parses_fenced_json_result() -> None:
    payload = ClaudeWorkerAdapter._parse_result_text(
        '```json\n{"title":"Lantern Vale","summary":"Restore the valley.","genre":"cozy strategy"}\n```'
    )

    assert payload.title == "Lantern Vale"
    assert payload.summary == "Restore the valley."
    assert payload.genre == "cozy strategy"


def test_adapter_parses_fenced_yaml_result() -> None:
    payload = ClaudeWorkerAdapter._parse_result_text(
        "```yaml\n"
        "title: Lantern Vale\n"
        "summary: Restore the valley.\n"
        "genre: cozy strategy\n"
        "```\n"
    )

    assert payload.title == "Lantern Vale"
    assert payload.summary == "Restore the valley."
    assert payload.genre == "cozy strategy"
