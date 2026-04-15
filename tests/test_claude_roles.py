from __future__ import annotations

import subprocess
import argparse
from argparse import Namespace

import pytest

from studio.llm import (
    ArtPayload,
    ClaudeRoleAdapter,
    ClaudeRoleError,
    DesignPayload,
    QaPayload,
    QualityPayload,
    ReviewerPayload,
    parse_role_payload,
)
from studio.llm import claude_roles as claude_roles_module


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


def test_supported_role_registry_includes_qa_with_other_active_roles() -> None:
    assert claude_roles_module._ACTIVE_ROLE_NAMES == {"art", "dev", "design", "qa", "quality", "reviewer"}
    assert set(claude_roles_module._ROLE_PAYLOAD_MODELS) == {
        "art",
        "dev",
        "design",
        "qa",
        "quality",
        "reviewer",
    }


def test_prompt_includes_qa_contract_keywords() -> None:
    prompt = ClaudeRoleAdapter._prompt("qa", {"feature": "photo mode", "requirement_id": "req_001"})

    assert "qa" in prompt
    assert "passed" in prompt
    assert "suggested_bug" in prompt


def test_prompt_includes_reviewer_contract_keywords() -> None:
    prompt = ClaudeRoleAdapter._prompt("reviewer", {"feature": "photo mode", "requirement_id": "req_001"})

    assert "reviewer" in prompt
    assert "decision" in prompt
    assert "reason" in prompt
    assert "risks" in prompt


def test_output_format_fails_fast_when_active_role_is_missing_schema(monkeypatch) -> None:
    patched = dict(claude_roles_module._ROLE_OUTPUT_FORMATS)
    patched.pop("dev")
    monkeypatch.setattr(claude_roles_module, "_ROLE_OUTPUT_FORMATS", patched)

    with pytest.raises(ClaudeRoleError, match="missing_output_format:dev"):
        ClaudeRoleAdapter._output_format("dev")


def test_adapter_does_not_expose_build_prompt() -> None:
    assert not hasattr(ClaudeRoleAdapter, "build_prompt")


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
    adapter = ClaudeRoleAdapter(project_root=tmp_path)
    expected = ReviewerPayload(
        decision="continue",
        reason="subprocess fallback succeeded",
        risks=[],
    )

    async def fake_generate_payload(
        role_name: str, context: dict[str, object], config: object
    ) -> ReviewerPayload:
        raise ClaudeRoleError("Failed to start Claude Code: Blocking call to os.getcwd")

    def fake_generate_payload_via_subprocess(role_name: str, context: dict[str, object]) -> ReviewerPayload:
        assert role_name == "reviewer"
        assert context == {"feature": "photo mode"}
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
        role_name: str, context: dict[str, object], config: object
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
    adapter = ClaudeRoleAdapter(project_root=tmp_path)
    expected = ReviewerPayload(
        decision="continue",
        reason="loop-safe subprocess path",
        risks=[],
    )

    async def fake_generate_payload(
        role_name: str, context: dict[str, object], config: object
    ) -> ReviewerPayload:
        raise AssertionError("async path should not run under an active event loop")

    def fake_generate_payload_via_subprocess(role_name: str, context: dict[str, object]) -> ReviewerPayload:
        assert role_name == "reviewer"
        assert context == {"feature": "photo mode"}
        return expected

    monkeypatch.setattr(adapter, "_generate_payload", fake_generate_payload)
    monkeypatch.setattr(adapter, "_generate_payload_via_subprocess", fake_generate_payload_via_subprocess)

    payload = adapter.generate("reviewer", {"feature": "photo mode"})

    assert payload == expected


def test_subprocess_fallback_sends_context_via_stdin(monkeypatch, tmp_path) -> None:
    adapter = ClaudeRoleAdapter(project_root=tmp_path)
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

    monkeypatch.setattr(subprocess, "run", fake_run)

    payload = adapter._generate_payload_via_subprocess("reviewer", {"feature": "photo mode"})

    assert payload == ReviewerPayload(
        decision="continue",
        reason="stdin transport",
        risks=[],
    )
    assert "-m" not in calls["cmd"]
    assert str(claude_roles_module.Path(claude_roles_module.__file__).resolve()) in calls["cmd"]
    assert "--context-json" not in calls["cmd"]
    assert calls["kwargs"]["input"] == '{"feature": "photo mode"}'


def test_subprocess_fallback_wraps_transport_errors(monkeypatch, tmp_path) -> None:
    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("spawn failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="spawn failed"):
        adapter._generate_payload_via_subprocess("reviewer", {"feature": "photo mode"})


def test_subprocess_fallback_wraps_timeout_errors(monkeypatch, tmp_path) -> None:
    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="300"):
        adapter._generate_payload_via_subprocess("reviewer", {"feature": "photo mode"})


def test_subprocess_fallback_rejects_unsupported_roles_before_spawn(monkeypatch, tmp_path) -> None:
    adapter = ClaudeRoleAdapter(project_root=tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("subprocess should not run")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ClaudeRoleError, match="unsupported_role:planner"):
        adapter._generate_payload_via_subprocess("planner", {"feature": "photo mode"})


def test_main_rejects_unsupported_roles_before_generation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(project_root=str(tmp_path), role_name="planner"),
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
        lambda self: Namespace(project_root=str(tmp_path), role_name="reviewer"),
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
