from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from studio.observability.claude_code_hook import (
    HookResult,
    agent_role_from_project_dir,
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


def test_run_hook_exits_zero_when_disabled() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "false"},
    )

    assert result == HookResult(exit_code=0, message="Langfuse tracing disabled")


def test_run_hook_exits_zero_when_credentials_missing() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "true"},
    )

    assert result.exit_code == 0
    assert result.message == "Langfuse credentials missing"


def test_run_hook_calls_process_transcript_with_payload(tmp_path: Path) -> None:
    with patch(
        "studio.observability.langfuse_tracer.process_transcript",
        return_value="Processed 2 turns",
    ) as mock_process:
        result = run_hook(
            stdin_text='{"session_id":"s1","transcript_path":"/tmp/t.jsonl"}',
            environ={
                "TRACE_TO_LANGFUSE": "true",
                "LANGFUSE_PUBLIC_KEY": "pk",
                "LANGFUSE_SECRET_KEY": "sk",
                "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
                "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "design"),
            },
        )

        assert result == HookResult(exit_code=0, message="Processed 2 turns")
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[0][0] == '{"session_id":"s1","transcript_path":"/tmp/t.jsonl"}'
        delegated_env = call_args[1]["environ"]
        assert delegated_env["CC_LANGFUSE_AGENT_ROLE"] == "design"


def test_run_hook_fails_open_on_exception() -> None:
    with patch(
        "studio.observability.langfuse_tracer.process_transcript",
        side_effect=RuntimeError("mock error"),
    ):
        result = run_hook(
            stdin_text='{"session_id":"s1"}',
            environ={
                "TRACE_TO_LANGFUSE": "true",
                "LANGFUSE_PUBLIC_KEY": "pk",
                "LANGFUSE_SECRET_KEY": "sk",
                "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            },
        )

        assert result.exit_code == 0
        assert "fail" in result.message.lower()


def test_shared_hook_script_exists_and_uses_wrapper() -> None:
    script = Path(".claude/hooks/langfuse_hook.py")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "from studio.observability.claude_code_hook import main" in content


AGENT_NAMES = [
    "art",
    "delivery_planner",
    "design",
    "dev",
    "moderator",
    "qa",
    "quality",
    "requirement_clarifier",
    "reviewer",
    "worker",
]

EXPECTED_AGENT_PERMISSIONS = {
    "art": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "delivery_planner": {"allow": ["Bash(*)", "Edit(*)"]},
    "design": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "dev": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "moderator": {
        "allow": ["Read(*)", "Glob(*)", "Grep(*)"],
        "deny": ["Bash(*)", "Edit(*)", "Write(*)"],
    },
    "qa": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "quality": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "requirement_clarifier": {
        "allow": ["Read(*)", "Glob(*)", "Grep(*)"],
        "deny": ["Bash(*)", "Edit(*)", "Write(*)"],
    },
    "reviewer": {"allow": ["Bash(*)", "Edit(*)", "Write(*)", "Read(*)", "Glob(*)", "Grep(*)", "LS(*)", "MultiEdit(*)"]},
    "worker": {"allow": ["Bash(*)", "Edit(*)"]},
}


def test_all_agent_settings_have_langfuse_stop_hook() -> None:
    expected_command = 'uv run python "../../hooks/langfuse_hook.py"'

    for agent_name in AGENT_NAMES:
        path = Path(".claude") / "agents" / agent_name / ".claude" / "settings.local.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["env"]["TRACE_TO_LANGFUSE"] == "true"
        assert data["hooks"]["Stop"][0]["hooks"][0] == {
            "type": "command",
            "command": expected_command,
        }


def test_all_agent_settings_preserve_permissions() -> None:
    for agent_name in AGENT_NAMES:
        path = Path(".claude") / "agents" / agent_name / ".claude" / "settings.local.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["permissions"] == EXPECTED_AGENT_PERMISSIONS[agent_name]
