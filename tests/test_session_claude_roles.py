from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from studio.agents import AgentProfile
from studio.llm.claude_roles import ClaudeRoleAdapter, ClaudeRoleConfig
from studio.llm import claude_roles as cr_module


def _fake_profile(tmp_path: Path) -> AgentProfile:
    return AgentProfile(
        name="test",
        system_prompt="Test system prompt.",
        claude_project_root=tmp_path,
    )


def test_adapter_stores_session_id():
    adapter = ClaudeRoleAdapter(session_id="sess-123")
    assert adapter.session_id == "sess-123"


def test_adapter_defaults_session_id_to_none():
    adapter = ClaudeRoleAdapter()
    assert adapter.session_id is None


def test_subprocess_payload_path_passes_session_id(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"agenda":["test"],"attendees":["dev"],"focus_questions":[]}',
            stderr="",
        )

    monkeypatch.setattr(cr_module.subprocess, "run", fake_run)

    adapter = ClaudeRoleAdapter(
        session_id="sess-123",
        project_root=tmp_path,
        profile=_fake_profile(tmp_path),
    )

    adapter._generate_payload_via_subprocess(
        "moderator_prepare",
        {"goal": {"prompt": "test"}},
        adapter.debug_prompt("moderator_prepare", {"goal": {"prompt": "test"}}),
    )

    cmd = captured["cmd"]
    assert "--session-id" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "sess-123"


def test_chat_subprocess_path_passes_session_id(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="chat reply",
            stderr="",
        )

    monkeypatch.setattr(cr_module.subprocess, "run", fake_run)

    adapter = ClaudeRoleAdapter(
        session_id="sess-123",
        project_root=tmp_path,
        profile=_fake_profile(tmp_path),
    )

    assert adapter._chat_via_subprocess("hello") == "chat reply"

    cmd = captured["cmd"]
    assert "--session-id" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "sess-123"


@pytest.mark.anyio
async def test_generate_payload_passes_session_id_to_sdk_options(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        yield cr_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-123",
            structured_output={
                "agenda": ["test"],
                "attendees": ["dev"],
                "focus_questions": [],
            },
        )

    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(
        session_id="sess-123",
        project_root=tmp_path,
        profile=_fake_profile(tmp_path),
    )
    config = ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None)
    prompt = adapter.debug_prompt("moderator_prepare", {"goal": {"prompt": "test"}})

    await adapter._generate_payload("moderator_prepare", {"goal": {"prompt": "test"}}, config, prompt)
    opts = captured_options["options"]
    assert opts.session_id == "sess-123"
    assert opts.continue_conversation is True


@pytest.mark.anyio
async def test_generate_payload_omits_session_id_when_none(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        yield cr_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="new",
            structured_output={
                "agenda": ["test"],
                "attendees": ["dev"],
                "focus_questions": [],
            },
        )

    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_fake_profile(tmp_path),
    )
    config = ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None)
    prompt = adapter.debug_prompt("moderator_prepare", {"goal": {"prompt": "test"}})

    await adapter._generate_payload("moderator_prepare", {"goal": {"prompt": "test"}}, config, prompt)
    opts = captured_options["options"]
    assert opts.session_id is None
    assert opts.continue_conversation is False


@pytest.mark.anyio
async def test_chat_passes_session_id_to_sdk_options(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}

    async def fake_query(*, prompt: str, options: object):
        captured_options["options"] = options
        yield cr_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-123",
            result="chat reply",
        )

    monkeypatch.setattr(cr_module, "query", fake_query)

    adapter = ClaudeRoleAdapter(
        session_id="sess-123",
        project_root=tmp_path,
        profile=_fake_profile(tmp_path),
    )
    config = ClaudeRoleConfig(enabled=True, mode="text", model=None, api_key="key", base_url=None)

    result = await adapter._chat("hello", config)
    assert result == "chat reply"
    opts = captured_options["options"]
    assert opts.session_id == "sess-123"
    assert opts.continue_conversation is True
