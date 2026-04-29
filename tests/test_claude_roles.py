from __future__ import annotations

import argparse
import os
import subprocess
import sys
from argparse import Namespace

import pytest
from claude_agent_sdk.types import AssistantMessage, TextBlock

from studio.agents import AgentProfile
from studio.llm import (
    ArtPayload,
    ClaudeRoleAdapter,
    ClaudeRoleError,
    DesignPayload,
    QaPayload,
    QualityPayload,
    ReviewerPayload,
    WorkerPayload,
    parse_role_payload,
)
from studio.llm import claude_roles as claude_roles_module
from studio.runtime import process_registry


def _profile(*, name: str, system_prompt: str, claude_project_root) -> AgentProfile:
    return AgentProfile(
        name=name,
        system_prompt=system_prompt,
        claude_project_root=claude_project_root,
    )


def test_parse_role_payload_returns_reviewer_payload() -> None:
    payload = parse_role_payload(
        "reviewer",
        {"decision": "continue", "reason": "looks good", "risks": ["minor polish"]},
    )

    assert payload == ReviewerPayload(
        decision="continue",
        reason="looks good",
        risks=["minor polish"],
    )


def test_parse_role_payload_returns_design_payload() -> None:
    payload = parse_role_payload(
        "design",
        {
            "title": "Lantern Vale",
            "summary": "Restore the valley with patient strategy.",
            "core_rules": ["Guide villagers to relight shrines."],
            "acceptance_criteria": ["Players can complete a full restoration loop."],
            "open_questions": ["How many shrines should the first region contain?"],
        },
    )

    assert payload == DesignPayload(
        title="Lantern Vale",
        summary="Restore the valley with patient strategy.",
        core_rules=["Guide villagers to relight shrines."],
        acceptance_criteria=["Players can complete a full restoration loop."],
        open_questions=["How many shrines should the first region contain?"],
    )


def test_parse_role_payload_returns_qa_payload() -> None:
    payload = parse_role_payload(
        "qa",
        {
            "summary": "Validated the playable loop with a stable smoke pass.",
            "passed": True,
            "suggested_bug": "Camera jitter appears after shrine completion.",
        },
    )

    assert payload == QaPayload(
        summary="Validated the playable loop with a stable smoke pass.",
        passed=True,
        suggested_bug="Camera jitter appears after shrine completion.",
    )


def test_parse_role_payload_returns_quality_payload() -> None:
    payload = parse_role_payload(
        "quality",
        {
            "summary": "Ready for release candidate review.",
            "ready": True,
            "risks": ["Economy balance still needs monitoring."],
            "follow_ups": ["Run a final controller smoke pass."],
        },
    )

    assert payload == QualityPayload(
        summary="Ready for release candidate review.",
        ready=True,
        risks=["Economy balance still needs monitoring."],
        follow_ups=["Run a final controller smoke pass."],
    )


def test_parse_role_payload_returns_art_payload() -> None:
    payload = parse_role_payload(
        "art",
        {
            "summary": "Defines a cozy painterly direction.",
            "style_direction": "storybook watercolor",
            "asset_list": ["hero portrait", "shrine icon", "village tileset"],
        },
    )

    assert payload == ArtPayload(
        summary="Defines a cozy painterly direction.",
        style_direction="storybook watercolor",
        asset_list=["hero portrait", "shrine icon", "village tileset"],
    )


def test_parse_role_payload_returns_worker_payload() -> None:
    payload = parse_role_payload(
        "worker",
        {
            "title": "Lantern Vale",
            "summary": "Restore the valley.",
            "genre": "cozy strategy",
        },
    )

    assert payload == WorkerPayload(
        title="Lantern Vale",
        summary="Restore the valley.",
        genre="cozy strategy",
    )


def test_parse_role_payload_returns_moderator_discussion_payload() -> None:
    payload = parse_role_payload(
        "moderator_discussion",
        {
            "supplementary": {
                "Scope vs schedule": "Ship the smaller milestone first and defer stretch goals."
            },
            "unresolved_conflicts": ["Final platform target is still undecided."],
        },
    )

    assert isinstance(payload, claude_roles_module.ModeratorDiscussionPayload)
    assert payload == claude_roles_module.ModeratorDiscussionPayload(
        supplementary={
            "Scope vs schedule": "Ship the smaller milestone first and defer stretch goals."
        },
        unresolved_conflicts=["Final platform target is still undecided."],
    )


def test_parse_role_payload_rejects_invalid_reviewer_output() -> None:
    with pytest.raises(ClaudeRoleError, match="invalid_claude_output"):
        parse_role_payload("reviewer", {"decision": "ship-it"})


def test_extract_result_payload_parses_json_code_fence() -> None:
    payload = ClaudeRoleAdapter._parse_result_text(
        "下面是评审结果：\n```json\n"
        '{"decision":"continue","reason":"looks good","risks":[]}\n'
        "```"
    )

    assert payload == {"decision": "continue", "reason": "looks good", "risks": []}


def test_extract_result_payload_parses_embedded_json_object() -> None:
    payload = ClaudeRoleAdapter._parse_result_text(
        '评审通过。JSON 如下：{"decision":"continue","reason":"looks good","risks":[]}'
    )

    assert payload == {"decision": "continue", "reason": "looks good", "risks": []}


def test_supported_role_registry_includes_moderator_discussion() -> None:
    assert claude_roles_module._ACTIVE_ROLE_NAMES == {
        "agent_opinion",
        "art",
        "delivery_planner",
        "dev",
        "design",
        "moderator_discussion",
        "moderator_minutes",
        "moderator_prepare",
        "moderator_summary",
        "qa",
        "quality",
        "requirement_clarifier",
        "reviewer",
        "worker",
    }
    assert set(claude_roles_module._ROLE_PAYLOAD_MODELS) == {
        "agent_opinion",
        "art",
        "delivery_planner",
        "dev",
        "design",
        "moderator_discussion",
        "moderator_minutes",
        "moderator_prepare",
        "moderator_summary",
        "qa",
        "quality",
        "requirement_clarifier",
        "reviewer",
        "worker",
    }


def test_supported_role_registry_includes_requirement_clarifier() -> None:
    assert "requirement_clarifier" in claude_roles_module._ACTIVE_ROLE_NAMES
    assert "requirement_clarifier" in claude_roles_module._ROLE_PAYLOAD_MODELS
    assert "requirement_clarifier" in claude_roles_module._ROLE_OUTPUT_FORMATS


def test_prompt_uses_profile_system_prompt_for_qa(tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "qa"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="qa",
            system_prompt="QA profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    prompt = adapter.debug_prompt("qa", {"feature": "photo mode", "requirement_id": "req_001"})

    assert prompt.startswith("QA profile system prompt")
    assert "Context:" in prompt
    assert '"feature": "photo mode"' in prompt
    assert "passed" in prompt
    assert "suggested_bug" in prompt
    assert "You are the qa role." not in prompt


def test_prompt_uses_profile_system_prompt_for_reviewer(tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    prompt = adapter.debug_prompt("reviewer", {"feature": "photo mode", "requirement_id": "req_001"})

    assert prompt.startswith("Reviewer profile system prompt")
    assert "Context:" in prompt
    assert "decision" in prompt
    assert "reason" in prompt
    assert "risks" in prompt
    assert "You are the reviewer role." not in prompt


def test_output_format_fails_fast_when_active_role_is_missing_schema(monkeypatch) -> None:
    patched = dict(claude_roles_module._ROLE_OUTPUT_FORMATS)
    patched.pop("dev")
    monkeypatch.setattr(claude_roles_module, "_ROLE_OUTPUT_FORMATS", patched)

    with pytest.raises(ClaudeRoleError, match="missing_output_format:dev"):
        ClaudeRoleAdapter._output_format("dev")


def test_adapter_does_not_expose_build_prompt() -> None:
    assert not hasattr(ClaudeRoleAdapter, "build_prompt")


@pytest.mark.anyio
async def test_generate_uses_profile_claude_project_root_for_sdk(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    captured: dict[str, object] = {}

    async def fake_query(*, prompt: str, options: object):
        captured["prompt"] = prompt
        captured["cwd"] = getattr(options, "cwd")
        yield claude_roles_module.ResultMessage(
            subtype="result",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-1",
            structured_output={"decision": "continue", "reason": "ok", "risks": []},
        )

    monkeypatch.setattr(claude_roles_module, "query", fake_query)

    payload = await adapter._generate_payload(
        "reviewer",
        {"feature": "photo mode"},
        claude_roles_module.ClaudeRoleConfig(
            enabled=True,
            mode="text",
            model=None,
            api_key="test-key",
            base_url=None,
        ),
        adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
    )

    assert payload == ReviewerPayload(decision="continue", reason="ok", risks=[])
    assert captured["cwd"] == claude_root
    assert str(captured["prompt"]).startswith("Reviewer profile system prompt")
    assert '"feature": "photo mode"' in str(captured["prompt"])


@pytest.mark.anyio
async def test_generate_parses_assistant_text_when_result_message_is_missing(
    monkeypatch, tmp_path
) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    async def fake_query(*, prompt: str, options: object):
        yield AssistantMessage(
            content=[
                TextBlock(
                    text=(
                        "```json\n"
                        '{"decision":"continue","reason":"ok","risks":[]}\n'
                        "```"
                    )
                )
            ],
            model="glm-4.7",
            session_id="session-1",
        )

    monkeypatch.setattr(claude_roles_module, "query", fake_query)

    payload = await adapter._generate_payload(
        "reviewer",
        {"feature": "photo mode"},
        claude_roles_module.ClaudeRoleConfig(
            enabled=True,
            mode="text",
            model=None,
            api_key="test-key",
            base_url=None,
        ),
        adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
    )

    assert payload == ReviewerPayload(decision="continue", reason="ok", risks=[])


def test_load_config_reads_claude_settings_from_dotenv(tmp_path) -> None:
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

    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    config = adapter.load_config()

    assert config.enabled is True
    assert config.mode == "text"
    assert config.model is None
    assert config.api_key == "test-key"
    assert config.base_url is None


def test_load_config_resolves_enclosing_repo_root_for_nested_workspaces(tmp_path) -> None:
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
    (tmp_path / "studio" / "agents" / "profiles").mkdir(parents=True)
    nested_workspace = tmp_path / ".e2e-workspaces" / "run-1" / "workspace"
    nested_workspace.mkdir(parents=True)

    adapter = ClaudeRoleAdapter(project_root=nested_workspace)

    config = adapter.load_config()

    assert config.enabled is True
    assert config.mode == "text"
    assert config.api_key == "test-key"


def test_generate_falls_back_to_subprocess_for_blocking_getcwd(monkeypatch, tmp_path) -> None:
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
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    expected = ReviewerPayload(
        decision="continue",
        reason="subprocess fallback succeeded",
        risks=[],
    )

    async def fake_generate_payload(
        role_name: str, context: dict[str, object], config: object, prompt: str
    ) -> ReviewerPayload:
        raise ClaudeRoleError("Failed to start Claude Code: Blocking call to os.getcwd")

    def fake_generate_payload_via_subprocess(
        role_name: str, context: dict[str, object], prompt: str
    ) -> ReviewerPayload:
        assert role_name == "reviewer"
        assert context == {"feature": "photo mode"}
        assert "Context:" in prompt
        return expected

    monkeypatch.setattr(adapter, "_generate_payload", fake_generate_payload)
    monkeypatch.setattr(adapter, "_generate_payload_via_subprocess", fake_generate_payload_via_subprocess)

    payload = adapter.generate("reviewer", {"feature": "photo mode"})

    assert payload == expected


def test_generate_rejects_unsupported_roles_before_invocation(monkeypatch, tmp_path) -> None:
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
    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    async def fake_generate_payload(
        role_name: str, context: dict[str, object], config: object, prompt: str
    ) -> ReviewerPayload:
        raise AssertionError("generation path should not run")

    monkeypatch.setattr(adapter, "_generate_payload", fake_generate_payload)

    with pytest.raises(ClaudeRoleError, match="unsupported_role:planner"):
        adapter.generate("planner", {"feature": "photo mode"})


@pytest.mark.anyio
async def test_generate_uses_subprocess_when_called_from_running_event_loop(monkeypatch, tmp_path) -> None:
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
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    expected = ReviewerPayload(
        decision="continue",
        reason="loop-safe subprocess path",
        risks=[],
    )

    async def fake_generate_payload(
        role_name: str, context: dict[str, object], config: object, prompt: str
    ) -> ReviewerPayload:
        raise AssertionError("async path should not run under an active event loop")

    def fake_generate_payload_via_subprocess(
        role_name: str, context: dict[str, object], prompt: str
    ) -> ReviewerPayload:
        assert role_name == "reviewer"
        assert context == {"feature": "photo mode"}
        assert "Context:" in prompt
        return expected

    monkeypatch.setattr(adapter, "_generate_payload", fake_generate_payload)
    monkeypatch.setattr(adapter, "_generate_payload_via_subprocess", fake_generate_payload_via_subprocess)

    payload = adapter.generate("reviewer", {"feature": "photo mode"})

    assert payload == expected


def test_subprocess_fallback_sends_context_via_stdin(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    calls: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"decision":"continue","reason":"stdin transport","risks":[]}',
            stderr="",
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    payload = adapter._generate_payload_via_subprocess(
        "reviewer",
        {"feature": "photo mode"},
        adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
    )

    assert payload == ReviewerPayload(
        decision="continue",
        reason="stdin transport",
        risks=[],
    )
    assert "-m" not in calls["cmd"]
    assert str(claude_roles_module.Path(claude_roles_module.__file__).resolve()) in calls["cmd"]
    assert "--context-json" not in calls["cmd"]
    assert calls["kwargs"]["cwd"] == claude_root
    assert str(tmp_path) in calls["kwargs"]["env"]["PYTHONPATH"]
    assert calls["kwargs"]["input"] == '{"feature": "photo mode"}'
    assert calls["kwargs"]["purpose"] == "claude_role:reviewer"


def test_subprocess_fallback_uses_configured_timeout(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
        timeout_seconds=12,
    )
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"decision":"continue","reason":"configured timeout","risks":[]}',
            stderr="",
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    adapter._generate_payload_via_subprocess(
        "reviewer",
        {"feature": "photo mode"},
        adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
    )

    assert captured["timeout"] == 12


def test_subprocess_fallback_replaces_invalid_output_bytes(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["errors"] = kwargs.get("errors")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"decision":"continue","reason":"decode-safe","risks":[]}',
            stderr="",
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    payload = adapter._generate_payload_via_subprocess(
        "reviewer",
        {"feature": "photo mode"},
        adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
    )

    assert captured["errors"] == "replace"
    assert payload.reason == "decode-safe"


def test_subprocess_fallback_rejects_missing_stdout(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=None,
            stderr=None,
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="missing_claude_result"):
        adapter._generate_payload_via_subprocess(
            "reviewer",
            {"feature": "photo mode"},
            adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
        )


def test_role_script_runs_from_claude_project_root_without_pythonpath(tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    script_path = claude_roles_module.Path(claude_roles_module.__file__).resolve()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=claude_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )

    assert proc.returncode == 0
    assert "usage:" in proc.stdout


def test_subprocess_fallback_wraps_transport_errors(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("spawn failed")

    monkeypatch.setattr(process_registry, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="spawn failed"):
        adapter._generate_payload_via_subprocess(
            "reviewer",
            {"feature": "photo mode"},
            adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
        )


def test_subprocess_fallback_wraps_timeout_errors(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=claude_root,
        ),
    )

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(process_registry, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="300"):
        adapter._generate_payload_via_subprocess(
            "reviewer",
            {"feature": "photo mode"},
            adapter.debug_prompt("reviewer", {"feature": "photo mode"}),
        )


def test_subprocess_fallback_rejects_unsupported_roles_before_spawn(monkeypatch, tmp_path) -> None:
    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("subprocess should not run")

    monkeypatch.setattr(process_registry, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="unsupported_role:planner"):
        adapter._generate_payload_via_subprocess(
            "planner",
            {"feature": "photo mode"},
            "planner prompt",
        )


def test_main_rejects_unsupported_roles_before_generation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(
            project_root=str(tmp_path),
            role_name="planner",
            system_prompt="Planner profile system prompt",
            claude_project_root=str(tmp_path),
        ),
    )

    def fake_load_config(self: ClaudeRoleAdapter) -> claude_roles_module.ClaudeRoleConfig:
        return claude_roles_module.ClaudeRoleConfig(
            enabled=True,
            mode="text",
            model=None,
            api_key="test-key",
            base_url=None,
        )

    async def fake_generate_payload(
        self: ClaudeRoleAdapter,
        role_name: str,
        context: dict[str, object],
        config: object,
        prompt: str,
    ) -> ReviewerPayload:
        raise AssertionError("generation path should not run")

    monkeypatch.setattr(ClaudeRoleAdapter, "load_config", fake_load_config)
    monkeypatch.setattr(ClaudeRoleAdapter, "_generate_payload", fake_generate_payload)
    monkeypatch.setattr(claude_roles_module.sys, "stdin", type("FakeStdin", (), {"read": lambda self: "{}"})())

    assert claude_roles_module._main() == 1


def test_main_returns_clean_error_for_generation_failure(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(
            project_root=str(tmp_path),
            role_name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=str(tmp_path),
        ),
    )

    def fake_load_config(self: ClaudeRoleAdapter) -> claude_roles_module.ClaudeRoleConfig:
        return claude_roles_module.ClaudeRoleConfig(
            enabled=True,
            mode="text",
            model=None,
            api_key="test-key",
            base_url=None,
        )

    async def fake_generate_payload(
        self: ClaudeRoleAdapter,
        role_name: str,
        context: dict[str, object],
        config: object,
        prompt: str,
    ) -> ReviewerPayload:
        raise ClaudeRoleError("invalid_claude_output")

    monkeypatch.setattr(ClaudeRoleAdapter, "load_config", fake_load_config)
    monkeypatch.setattr(ClaudeRoleAdapter, "_generate_payload", fake_generate_payload)
    monkeypatch.setattr(claude_roles_module.sys, "stdin", type("FakeStdin", (), {"read": lambda self: "{}"})())

    exit_code = claude_roles_module._main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.strip() == "invalid_claude_output"


def test_main_rejects_incomplete_profile_cli_args_before_loading_config(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(
            project_root=str(tmp_path),
            role_name="reviewer",
            system_prompt="Reviewer profile system prompt",
            claude_project_root=None,
        ),
    )

    def fail_load_config(self: ClaudeRoleAdapter) -> claude_roles_module.ClaudeRoleConfig:
        raise AssertionError("load_config should not run without a full profile")

    async def fail_generate_payload(
        self: ClaudeRoleAdapter,
        role_name: str,
        context: dict[str, object],
        config: object,
        prompt: str,
    ) -> ReviewerPayload:
        raise AssertionError("generation path should not run without a full profile")

    monkeypatch.setattr(ClaudeRoleAdapter, "load_config", fail_load_config)
    monkeypatch.setattr(ClaudeRoleAdapter, "_generate_payload", fail_generate_payload)
    monkeypatch.setattr(claude_roles_module.sys, "stdin", type("FakeStdin", (), {"read": lambda self: "{}"})())

    exit_code = claude_roles_module._main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.strip() == "missing_agent_profile"


def test_role_adapter_subprocess_env_includes_langfuse(tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GAME_STUDIO_LANGFUSE_ENABLED=true",
                "LANGFUSE_PUBLIC_KEY=pk",
                "LANGFUSE_SECRET_KEY=sk",
                "LANGFUSE_HOST=https://langfuse.example",
            ]
        ),
        encoding="utf-8",
    )
    profile = _profile(
        name="reviewer",
        system_prompt="review",
        claude_project_root=claude_root,
    )
    adapter = ClaudeRoleAdapter(project_root=tmp_path, profile=profile)

    env = adapter._subprocess_env()

    assert env["LANGFUSE_PUBLIC_KEY"] == "pk"
    assert env["LANGFUSE_SECRET_KEY"] == "sk"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"


def test_role_adapter_records_debug_metadata_from_observation(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GAME_STUDIO_CLAUDE_ENABLED=true",
                "ANTHROPIC_API_KEY=key",
                "GAME_STUDIO_LANGFUSE_ENABLED=true",
                "LANGFUSE_PUBLIC_KEY=pk",
                "LANGFUSE_SECRET_KEY=sk",
            ]
        ),
        encoding="utf-8",
    )
    profile = _profile(
        name="reviewer",
        system_prompt="review",
        claude_project_root=claude_root,
    )

    async def fake_generate_payload(self, role_name, context, config, prompt):
        self._last_debug_record = {
            "prompt": prompt,
            "context": context,
            "reply": {"decision": "continue", "reason": "ok", "risks": []},
        }
        return claude_roles_module.ReviewerPayload(
            decision="continue",
            reason="ok",
            risks=[],
        )

    monkeypatch.setattr(
        claude_roles_module.ClaudeRoleAdapter,
        "_generate_payload",
        fake_generate_payload,
    )

    adapter = ClaudeRoleAdapter(project_root=tmp_path, profile=profile)
    payload = adapter.generate("reviewer", {"prompt": "hello"})
    record = adapter.consume_debug_record()

    assert payload.decision == "continue"
    assert record is not None
    assert record["context"] == {"prompt": "hello"}
    assert "langfuse" in record
