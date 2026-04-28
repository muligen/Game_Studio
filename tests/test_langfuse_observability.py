from __future__ import annotations

from pathlib import Path

from studio.observability.langfuse import (
    LangfuseConfig,
    LangfuseTelemetry,
    _parse_bool,
    _parse_dotenv,
    redact,
)


def test_parse_dotenv_reads_langfuse_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GAME_STUDIO_LANGFUSE_ENABLED=true",
                "LANGFUSE_PUBLIC_KEY=pk-test",
                "LANGFUSE_SECRET_KEY=sk-test",
                "LANGFUSE_HOST=https://langfuse.example",
                "GAME_STUDIO_LANGFUSE_CAPTURE_IO=false",
                "GAME_STUDIO_LANGFUSE_SAMPLE_RATE=0.25",
            ]
        ),
        encoding="utf-8",
    )

    config = LangfuseConfig.from_env(tmp_path)

    assert config.enabled is True
    assert config.public_key == "pk-test"
    assert config.secret_key == "sk-test"
    assert config.host == "https://langfuse.example"
    assert config.capture_io is False
    assert config.sample_rate == 0.25


def test_missing_keys_disable_export(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "GAME_STUDIO_LANGFUSE_ENABLED=true\n",
        encoding="utf-8",
    )

    telemetry = LangfuseTelemetry.from_project_root(tmp_path)

    assert telemetry.enabled is False


def test_parse_bool_accepts_expected_values() -> None:
    assert _parse_bool("true") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True
    assert _parse_bool("false") is False
    assert _parse_bool("0") is False
    assert _parse_bool("") is False


def test_parse_dotenv_ignores_comments_and_empty_lines(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n# comment\nLANGFUSE_HOST='https://example.test'\nEMPTY=\n",
        encoding="utf-8",
    )

    values = _parse_dotenv(env_path)

    assert values == {"LANGFUSE_HOST": "https://example.test", "EMPTY": ""}


def test_redact_removes_sensitive_values_and_truncates_large_strings() -> None:
    payload = {
        "api_key": "secret-value",
        "nested": {
            "LANGFUSE_SECRET_KEY": "secret-value",
            "safe": "x" * 80,
        },
        "items": [{"token": "abc"}, "plain"],
    }

    redacted = redact(payload, max_string_length=20)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["LANGFUSE_SECRET_KEY"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "x" * 20 + "...[truncated]"
    assert redacted["items"][0]["token"] == "[REDACTED]"
    assert redacted["items"][1] == "plain"


def test_disabled_context_managers_are_noop(tmp_path: Path) -> None:
    telemetry = LangfuseTelemetry(config=LangfuseConfig(enabled=False))

    with telemetry.graph_trace(name="graph", metadata={"run_id": "run-1"}) as trace:
        with telemetry.node_span(name="node", metadata={"node_name": "worker"}) as span:
            span.update(output={"ok": True})
        trace.update(metadata={"done": True})

    assert telemetry.current_metadata() == {}


def test_fake_backend_records_trace_span_and_generation() -> None:
    telemetry = LangfuseTelemetry.fake()

    with telemetry.graph_trace(name="graph", metadata={"run_id": "run-1"}):
        with telemetry.node_span(name="worker", metadata={"node_name": "worker"}):
            with telemetry.llm_observation(
                name="claude:worker",
                metadata={"role_name": "worker"},
                input={"prompt": "hello"},
            ) as observation:
                observation.update(output={"title": "Demo"})

    assert [event["kind"] for event in telemetry.events] == [
        "trace_start",
        "span_start",
        "generation_start",
        "generation_update",
        "generation_end",
        "span_end",
        "trace_end",
    ]
    assert telemetry.events[2]["metadata"]["role_name"] == "worker"


def test_subprocess_env_includes_langfuse_settings_when_enabled() -> None:
    telemetry = LangfuseTelemetry(
        config=LangfuseConfig(
            enabled=True,
            public_key="pk",
            secret_key="sk",
            host="https://langfuse.example",
        )
    )

    env = telemetry.subprocess_env({"EXISTING": "1"})

    assert env["EXISTING"] == "1"
    assert env["LANGFUSE_PUBLIC_KEY"] == "pk"
    assert env["LANGFUSE_SECRET_KEY"] == "sk"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"
    assert env["GAME_STUDIO_LANGFUSE_ENABLED"] == "true"
