from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

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
    assert "llm_prompt" not in result.trace
    assert "llm_context" not in result.trace


def test_worker_falls_back_when_claude_disabled() -> None:
    result = WorkerAgent(claude_runner=FakeClaudeRunner(enabled=False)).run(_state())

    assert result.artifacts[0].payload["title"] == "Moonwell Garden"
    assert result.trace["fallback_used"] is True
    assert result.trace["fallback_reason"] == "claude_disabled"
    assert "llm_prompt" not in result.trace


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


def test_worker_runs_claude_generation_in_separate_thread() -> None:
    call_thread_ids: list[int] = []

    class ThreadAwareRunner(FakeClaudeRunner):
        def generate_design_brief(self, prompt: str) -> ClaudeWorkerPayload:
            call_thread_ids.append(threading.get_ident())
            return ClaudeWorkerPayload(
                title="Lantern Vale",
                summary="Restore the valley.",
                genre="cozy strategy",
            )

    main_thread_id = threading.get_ident()
    result = WorkerAgent(claude_runner=ThreadAwareRunner()).run(_state())

    assert result.trace["fallback_used"] is False
    assert call_thread_ids
    assert call_thread_ids[0] != main_thread_id


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


def test_worker_adapter_delegates_to_role_adapter() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRoleAdapter:
        def generate(self, role_name: str, context: dict[str, object]) -> dict[str, str]:
            calls.append((role_name, context))
            return {
                "title": "Lantern Vale",
                "summary": "Restore the valley.",
                "genre": "cozy strategy",
            }

    adapter = ClaudeWorkerAdapter(
        project_root=Path.cwd(),
        role_adapter=FakeRoleAdapter(),
    )

    payload = adapter.generate_design_brief("Design a simple 2D game concept")

    assert calls == [("worker", {"prompt": "Design a simple 2D game concept"})]
    assert isinstance(payload, ClaudeWorkerPayload)
    assert payload.title == "Lantern Vale"
    assert payload.summary == "Restore the valley."
    assert payload.genre == "cozy strategy"


def test_worker_adapter_accepts_typed_role_payload() -> None:
    class TypedRolePayload:
        title = "Shadow Hopper"
        summary = "A platformer about drifting through light and shadow."
        genre = "2D Platformer"

        def model_dump(self) -> dict[str, str]:
            return {
                "title": self.title,
                "summary": self.summary,
                "genre": self.genre,
            }

    class FakeRoleAdapter:
        def generate(self, role_name: str, context: dict[str, object]) -> TypedRolePayload:
            assert role_name == "worker"
            assert context == {"prompt": "Design a simple 2D game concept"}
            return TypedRolePayload()

    adapter = ClaudeWorkerAdapter(
        project_root=Path.cwd(),
        role_adapter=FakeRoleAdapter(),
    )

    payload = adapter.generate_design_brief("Design a simple 2D game concept")

    assert isinstance(payload, ClaudeWorkerPayload)
    assert payload.title == "Shadow Hopper"
    assert payload.summary == "A platformer about drifting through light and shadow."
    assert payload.genre == "2D Platformer"


def test_adapter_uses_subprocess_fallback_for_blocking_getcwd(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeWorkerAdapter(project_root=Path.cwd())

    async def _boom(prompt: str, config: object) -> ClaudeWorkerPayload:
        raise ClaudeWorkerError("Failed to start Claude Code: Blocking call to os.getcwd")

    monkeypatch.setattr(adapter, "_generate_design_brief", _boom)
    monkeypatch.setattr(
        adapter,
        "_generate_design_brief_via_subprocess",
        lambda prompt: ClaudeWorkerPayload(
            title="Shadow Hopper",
            summary="A platformer about drifting through light and shadow.",
            genre="2D Platformer",
        ),
    )

    monkeypatch.setattr(
        adapter,
        "load_config",
        lambda: SimpleNamespace(
            enabled=True,
            mode="text",
            model=None,
            api_key="set",
            base_url="set",
        ),
    )

    payload = adapter.generate_design_brief("Design a simple 2D game concept")

    assert payload.title == "Shadow Hopper"


def test_subprocess_parser_validates_json_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeWorkerAdapter(project_root=Path.cwd())
    monkeypatch.setattr(
        "studio.llm.claude_worker.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "title": "Lantern Vale",
                    "summary": "Restore the valley.",
                    "genre": "cozy strategy",
                }
            ),
            stderr="",
        ),
    )

    payload = adapter._generate_design_brief_via_subprocess("Design a simple 2D game concept")

    assert payload.genre == "cozy strategy"
