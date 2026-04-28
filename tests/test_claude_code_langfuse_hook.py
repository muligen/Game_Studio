from __future__ import annotations

import json
from pathlib import Path

from studio.observability.claude_code_hook import (
    HookResult,
    agent_role_from_project_dir,
    build_upstream_command,
    normalize_env,
    run_hook,
)


def test_agent_role_from_nested_claude_agent_dir() -> None:
    project_dir = Path("F:/projs/Game_Studio/.claude/agents/design")

    assert agent_role_from_project_dir(project_dir) == "design"


def test_agent_role_falls_back_to_directory_name() -> None:
    project_dir = Path("F:/tmp/custom-agent")

    assert agent_role_from_project_dir(project_dir) == "custom-agent"


def test_normalize_env_maps_langfuse_host_and_agent_environment(tmp_path: Path) -> None:
    env = normalize_env(
        {
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_HOST": "https://langfuse.example",
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "qa"),
        }
    )

    assert env["LANGFUSE_BASE_URL"] == "https://langfuse.example"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"
    assert env["CC_LANGFUSE_AGENT_ROLE"] == "qa"
    assert env["CC_LANGFUSE_ENVIRONMENT"] == "game-studio-qa"


def test_normalize_env_preserves_explicit_environment(tmp_path: Path) -> None:
    env = normalize_env(
        {
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            "CC_LANGFUSE_ENVIRONMENT": "local",
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "dev"),
        }
    )

    assert env["CC_LANGFUSE_ENVIRONMENT"] == "local"
    assert env["CC_LANGFUSE_AGENT_ROLE"] == "dev"


def test_build_upstream_command_uses_global_hook_project() -> None:
    env = {
        "USERPROFILE": "C:/Users/XSJ",
        "CC_LANGFUSE_HOOK_PROJECT": "C:/Users/XSJ/.claude/hooks/langfuse-claudecode",
    }

    command = build_upstream_command(env)

    assert command[:3] == ["uv", "run", "--project"]
    assert Path(command[3]) == Path("C:/Users/XSJ/.claude/hooks/langfuse-claudecode")
    assert command[4] == "python"
    assert Path(command[5]) == Path(
        "C:/Users/XSJ/.claude/hooks/langfuse-claudecode/langfuse_hook.py"
    )


def test_run_hook_exits_zero_when_disabled() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "false"},
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    assert result == HookResult(exit_code=0, message="Langfuse tracing disabled")


def test_run_hook_exits_zero_when_credentials_missing() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "true"},
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    assert result.exit_code == 0
    assert result.message == "Langfuse credentials missing"


def test_run_hook_delegates_payload_to_upstream(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    project = tmp_path / "langfuse-claudecode"
    project.mkdir()
    script = project / "langfuse_hook.py"
    script.write_text("print('hook')\n", encoding="utf-8")

    def fake_runner(command, *, input, text, env, capture_output):
        calls.append(
            {
                "command": command,
                "input": input,
                "text": text,
                "env": env,
                "capture_output": capture_output,
            }
        )

        class Completed:
            returncode = 0
            stderr = ""

        return Completed()

    result = run_hook(
        stdin_text='{"session_id":"s1"}',
        environ={
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            "CC_LANGFUSE_HOOK_PROJECT": str(project),
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "design"),
        },
        runner=fake_runner,
    )

    assert result == HookResult(exit_code=0, message="Langfuse hook delegated")
    assert calls[0]["input"] == '{"session_id":"s1"}'
    delegated_env = calls[0]["env"]
    assert delegated_env["CC_LANGFUSE_AGENT_ROLE"] == "design"
