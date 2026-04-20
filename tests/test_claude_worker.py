from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from studio.agents import AgentProfile
from studio.agents.worker import WorkerAgent
from studio.llm import ClaudeRoleAdapter
from studio.llm import claude_roles as claude_roles_module
from studio.llm.claude_worker import (
    ClaudeWorkerAdapter,
    ClaudeWorkerConfig,
    ClaudeWorkerError,
    ClaudeWorkerPayload,
)
from studio.llm import claude_worker as claude_worker_module
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


def _profile(*, system_prompt: str, claude_project_root: Path) -> AgentProfile:
    return AgentProfile(
        name="worker",
        system_prompt=system_prompt,
        claude_project_root=claude_project_root,
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


def test_worker_calls_claude_runner_directly() -> None:
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
    # Threading is now managed by the centralized pool at poller level,
    # so the agent call runs in the caller's thread.
    assert call_thread_ids[0] == main_thread_id


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


def test_worker_prompt_uses_profile_system_prompt(tmp_path: Path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "worker"
    claude_root.mkdir(parents=True)
    adapter = ClaudeWorkerAdapter(
        project_root=tmp_path,
        profile=_profile(
            system_prompt="Worker profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    prompt = adapter.debug_prompt("Design a simple 2D game concept")

    assert prompt.startswith("Worker profile system prompt")
    assert "Context:" in prompt
    assert '"prompt": "Design a simple 2D game concept"' in prompt
    assert "You are generating a compact game design brief." not in prompt


@pytest.mark.anyio
async def test_worker_generate_uses_profile_claude_project_root_for_sdk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "worker"
    claude_root.mkdir(parents=True)
    adapter = ClaudeWorkerAdapter(
        project_root=tmp_path,
        profile=_profile(
            system_prompt="Worker profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    captured: dict[str, object] = {}

    async def fake_query(*, prompt: str, options: object):
        captured["prompt"] = prompt
        captured["cwd"] = getattr(options, "cwd")
        yield claude_worker_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            structured_output={
                "title": "Lantern Vale",
                "summary": "Restore the valley.",
                "genre": "cozy strategy",
            },
        )

    monkeypatch.setattr(claude_worker_module, "query", fake_query)

    payload = await adapter._generate_design_brief(
        "Design a simple 2D game concept",
        claude_worker_module.ClaudeWorkerConfig(
            enabled=True,
            mode="text",
            model=None,
            api_key="test-key",
            base_url=None,
        ),
    )

    assert payload == ClaudeWorkerPayload(
        title="Lantern Vale",
        summary="Restore the valley.",
        genre="cozy strategy",
    )
    assert captured["cwd"] == claude_root
    assert str(captured["prompt"]).startswith("Worker profile system prompt")
    assert '"prompt": "Design a simple 2D game concept"' in str(captured["prompt"])


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


def test_worker_adapter_is_compatible_with_real_claude_role_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "worker"
    claude_root.mkdir(parents=True)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GAME_STUDIO_CLAUDE_ENABLED=true",
                "GAME_STUDIO_CLAUDE_MODE=text",
                "ANTHROPIC_API_KEY=test-key",
            ]
        ),
        encoding="utf-8",
    )
    profile = _profile(
        system_prompt="Worker profile system prompt",
        claude_project_root=claude_root,
    )

    async def fake_query(*, prompt: str, options: object):
        yield claude_roles_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            structured_output={
                "title": "Lantern Vale",
                "summary": "Restore the valley.",
                "genre": "cozy strategy",
            },
        )

    monkeypatch.setattr(claude_roles_module, "query", fake_query)

    adapter = ClaudeWorkerAdapter(
        project_root=tmp_path,
        profile=profile,
        role_adapter=ClaudeRoleAdapter(project_root=tmp_path, profile=profile),
    )

    payload = adapter.generate_design_brief("Design a simple 2D game concept")

    assert payload == ClaudeWorkerPayload(
        title="Lantern Vale",
        summary="Restore the valley.",
        genre="cozy strategy",
    )


def test_adapter_uses_subprocess_fallback_for_blocking_getcwd(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_root = Path.cwd() / ".claude" / "agents" / "worker"
    adapter = ClaudeWorkerAdapter(
        project_root=Path.cwd(),
        profile=_profile(
            system_prompt="Worker profile system prompt",
            claude_project_root=claude_root,
        ),
    )

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
    claude_root = Path.cwd() / ".claude" / "agents" / "worker"
    adapter = ClaudeWorkerAdapter(
        project_root=Path.cwd(),
        profile=_profile(
            system_prompt="Worker profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        "studio.llm.claude_worker.subprocess.run",
        lambda *args, **kwargs: calls.update({"args": args, "kwargs": kwargs}) or SimpleNamespace(
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
    assert calls["kwargs"]["cwd"] == claude_root
