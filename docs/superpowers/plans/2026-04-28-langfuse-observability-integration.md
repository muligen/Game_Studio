# Langfuse Observability Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional Langfuse observability for Game Studio LangGraph workflows and Claude Agent SDK calls without changing runtime behavior when Langfuse is disabled.

**Architecture:** Add a small `studio.observability` package that owns configuration, redaction, no-op behavior, Langfuse span wrappers, and subprocess environment propagation. Instrument Claude adapters first, then graph node boundaries, then enrich local LLM logs and docs.

**Tech Stack:** Python 3.12, LangGraph, Claude Agent SDK, Langfuse Python SDK, Pydantic-style payload normalization, pytest, uv.

---

## File Structure

- Create `studio/observability/__init__.py`
  - Exports the telemetry helpers used by runtime modules.
- Create `studio/observability/langfuse.py`
  - Owns Langfuse config parsing, no-op context managers, redaction, truncation, observation metadata, and subprocess env propagation.
- Create `tests/test_langfuse_observability.py`
  - Unit tests for config parsing, no-op mode, redaction, truncation, metadata context, and subprocess env propagation.
- Modify `pyproject.toml`
  - Add the Langfuse dependency.
- Modify `.env.example`
  - Add Langfuse environment variables.
- Modify `studio/llm/claude_roles.py`
  - Wrap role generation and chat calls in LLM observations.
  - Pass telemetry env to subprocess calls.
- Modify `studio/llm/claude_worker.py`
  - Wrap legacy worker calls in LLM observations.
  - Pass telemetry env to subprocess calls.
- Modify `studio/runtime/graph.py`
  - Add workflow traces and node spans around demo, design, delivery, and meeting graph nodes.
- Modify `studio/runtime/llm_logs.py`
  - Accept optional Langfuse metadata and persist it in local logs.
- Modify `README.md`
  - Document setup and manual verification.

## Task 1: Dependency and Environment Configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Test: none

- [ ] **Step 1: Add Langfuse dependency**

Modify `pyproject.toml` dependencies to include:

```toml
dependencies = [
  "claude-agent-sdk",
  "langgraph",
  "langchain-core",
  "langfuse>=3.0.0",
  "PyYAML>=6.0",
  "pydantic>=2.7",
  "typer>=0.12",
  "fastapi>=0.109.0",
  "uvicorn[standard]>=0.27.0",
  "watchdog>=4.0.0",
  "python-multipart>=0.0.9",
]
```

- [ ] **Step 2: Lock dependency**

Run:

```powershell
uv lock
```

Expected: `uv.lock` updates successfully and includes `langfuse`.

- [ ] **Step 3: Add Langfuse environment variables**

Append to `.env.example`:

```env
GAME_STUDIO_LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
GAME_STUDIO_LANGFUSE_CAPTURE_IO=true
GAME_STUDIO_LANGFUSE_SAMPLE_RATE=1.0
```

- [ ] **Step 4: Review diff**

Run:

```powershell
git diff -- pyproject.toml .env.example uv.lock
```

Expected: only dependency lock changes and Langfuse env defaults are present.

- [ ] **Step 5: Commit**

Run:

```powershell
git add pyproject.toml uv.lock .env.example
git commit -m "Add Langfuse configuration dependency"
```

Expected: commit succeeds.

## Task 2: Observability Module Tests

**Files:**
- Create: `tests/test_langfuse_observability.py`
- Create later: `studio/observability/__init__.py`
- Create later: `studio/observability/langfuse.py`

- [ ] **Step 1: Write failing tests for config, redaction, truncation, no-op, metadata, and env propagation**

Create `tests/test_langfuse_observability.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_langfuse_observability.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'studio.observability'`.

## Task 3: Observability Module Implementation

**Files:**
- Create: `studio/observability/__init__.py`
- Create: `studio/observability/langfuse.py`
- Test: `tests/test_langfuse_observability.py`

- [ ] **Step 1: Add package exports**

Create `studio/observability/__init__.py`:

```python
from studio.observability.langfuse import LangfuseConfig, LangfuseTelemetry

__all__ = ["LangfuseConfig", "LangfuseTelemetry"]
```

- [ ] **Step 2: Add telemetry implementation**

Create `studio/observability/langfuse.py`:

```python
from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off", ""}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "secret",
    "token",
    "password",
    "anthropic_api_key",
    "langfuse_secret_key",
)
_CURRENT_METADATA: contextvars.ContextVar[dict[str, object]] = contextvars.ContextVar(
    "game_studio_langfuse_metadata",
    default={},
)


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSEY:
        return False
    return default


def _parse_float(value: str | None, *, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(0.0, min(1.0, parsed))


def _is_sensitive_key(key: object) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any, *, max_string_length: int = 4000) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        if len(value) <= max_string_length:
            return value
        return value[:max_string_length] + "...[truncated]"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            redacted[key_str] = "[REDACTED]" if _is_sensitive_key(key_str) else redact(
                item,
                max_string_length=max_string_length,
            )
        return redacted
    if isinstance(value, (list, tuple)):
        return [redact(item, max_string_length=max_string_length) for item in value]
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return redact(value.model_dump(mode="json"), max_string_length=max_string_length)
    if hasattr(value, "__dict__"):
        return redact(vars(value), max_string_length=max_string_length)
    return redact(str(value), max_string_length=max_string_length)


@dataclass(frozen=True)
class LangfuseConfig:
    enabled: bool = False
    public_key: str | None = None
    secret_key: str | None = None
    host: str = "https://cloud.langfuse.com"
    capture_io: bool = True
    sample_rate: float = 1.0

    @property
    def export_enabled(self) -> bool:
        return bool(self.enabled and self.public_key and self.secret_key)

    @classmethod
    def from_env(cls, project_root: Path) -> "LangfuseConfig":
        values = _parse_dotenv(project_root / ".env")
        enabled = _parse_bool(values.get("GAME_STUDIO_LANGFUSE_ENABLED"), default=False)
        return cls(
            enabled=enabled,
            public_key=values.get("LANGFUSE_PUBLIC_KEY") or None,
            secret_key=values.get("LANGFUSE_SECRET_KEY") or None,
            host=values.get("LANGFUSE_HOST") or "https://cloud.langfuse.com",
            capture_io=_parse_bool(
                values.get("GAME_STUDIO_LANGFUSE_CAPTURE_IO"),
                default=True,
            ),
            sample_rate=_parse_float(
                values.get("GAME_STUDIO_LANGFUSE_SAMPLE_RATE"),
                default=1.0,
            ),
        )


class _Observation:
    def __init__(
        self,
        telemetry: "LangfuseTelemetry",
        *,
        kind: str,
        name: str,
        metadata: dict[str, object] | None = None,
        input: Any = None,
    ) -> None:
        self.telemetry = telemetry
        self.kind = kind
        self.name = name
        self.metadata = redact(metadata or {})
        self.input = redact(input) if telemetry.config.capture_io else None
        self.output: Any = None
        self.error: str | None = None

    def update(
        self,
        *,
        metadata: dict[str, object] | None = None,
        output: Any = None,
        error: BaseException | str | None = None,
    ) -> None:
        if metadata:
            self.metadata = {**self.metadata, **redact(metadata)}
        if output is not None and self.telemetry.config.capture_io:
            self.output = redact(output)
        if error is not None:
            self.error = str(error)
        self.telemetry._record(
            f"{self.kind}_update",
            self.name,
            metadata=self.metadata,
            input=self.input,
            output=self.output,
            error=self.error,
        )


class LangfuseTelemetry:
    def __init__(
        self,
        *,
        config: LangfuseConfig | None = None,
        backend: Any | None = None,
        record_events: bool = False,
    ) -> None:
        self.config = config or LangfuseConfig()
        self.backend = backend
        self.events: list[dict[str, Any]] = []
        self._record_events = record_events

    @property
    def enabled(self) -> bool:
        return self.config.export_enabled

    @classmethod
    def from_project_root(cls, project_root: Path) -> "LangfuseTelemetry":
        config = LangfuseConfig.from_env(project_root)
        return cls(config=config)

    @classmethod
    def fake(cls) -> "LangfuseTelemetry":
        return cls(
            config=LangfuseConfig(enabled=True, public_key="pk", secret_key="sk"),
            record_events=True,
        )

    def current_metadata(self) -> dict[str, object]:
        return dict(_CURRENT_METADATA.get())

    @contextmanager
    def graph_trace(
        self,
        *,
        name: str,
        metadata: dict[str, object],
        input: Any = None,
    ) -> Iterator[_Observation]:
        observation = _Observation(self, kind="trace", name=name, metadata=metadata, input=input)
        token = _CURRENT_METADATA.set({**self.current_metadata(), **observation.metadata})
        self._record("trace_start", name, metadata=observation.metadata, input=observation.input)
        try:
            yield observation
        except Exception as exc:
            observation.update(error=exc)
            raise
        finally:
            self._record("trace_end", name, metadata=observation.metadata, output=observation.output)
            _CURRENT_METADATA.reset(token)

    @contextmanager
    def node_span(
        self,
        *,
        name: str,
        metadata: dict[str, object],
        input: Any = None,
    ) -> Iterator[_Observation]:
        observation = _Observation(self, kind="span", name=name, metadata=metadata, input=input)
        self._record("span_start", name, metadata=observation.metadata, input=observation.input)
        try:
            yield observation
        except Exception as exc:
            observation.update(error=exc)
            raise
        finally:
            self._record("span_end", name, metadata=observation.metadata, output=observation.output)

    @contextmanager
    def llm_observation(
        self,
        *,
        name: str,
        metadata: dict[str, object],
        input: Any = None,
    ) -> Iterator[_Observation]:
        observation = _Observation(self, kind="generation", name=name, metadata=metadata, input=input)
        self._record(
            "generation_start",
            name,
            metadata=observation.metadata,
            input=observation.input,
        )
        try:
            yield observation
        except Exception as exc:
            observation.update(error=exc)
            raise
        finally:
            self._record(
                "generation_end",
                name,
                metadata=observation.metadata,
                output=observation.output,
                error=observation.error,
            )

    def subprocess_env(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(base_env or os.environ)
        if not self.config.export_enabled:
            return env
        env["GAME_STUDIO_LANGFUSE_ENABLED"] = "true"
        env["LANGFUSE_PUBLIC_KEY"] = self.config.public_key or ""
        env["LANGFUSE_SECRET_KEY"] = self.config.secret_key or ""
        env["LANGFUSE_HOST"] = self.config.host
        return env

    def _record(
        self,
        kind: str,
        name: str,
        *,
        metadata: dict[str, object] | None = None,
        input: Any = None,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        if not self._record_events:
            return
        self.events.append(
            {
                "kind": kind,
                "name": name,
                "metadata": metadata or {},
                "input": input,
                "output": output,
                "error": error,
            }
        )
```

- [ ] **Step 3: Run observability tests**

Run:

```powershell
uv run pytest tests/test_langfuse_observability.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```powershell
git add studio/observability tests/test_langfuse_observability.py
git commit -m "Add Langfuse telemetry wrapper"
```

Expected: commit succeeds.

## Task 4: Claude Role Adapter Instrumentation

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Test: `tests/test_claude_roles.py`

- [ ] **Step 1: Add failing tests for observation and subprocess env propagation**

Append to `tests/test_claude_roles.py`:

```python
def test_role_adapter_subprocess_env_includes_langfuse(monkeypatch, tmp_path) -> None:
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
    adapter = claude_roles_module.ClaudeRoleAdapter(project_root=tmp_path, profile=profile)

    env = adapter._subprocess_env()

    assert env["LANGFUSE_PUBLIC_KEY"] == "pk"
    assert env["LANGFUSE_SECRET_KEY"] == "sk"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"


def test_role_adapter_records_debug_metadata_from_observation(monkeypatch, tmp_path) -> None:
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

    adapter = claude_roles_module.ClaudeRoleAdapter(project_root=tmp_path, profile=profile)
    payload = adapter.generate("reviewer", {"prompt": "hello"})
    record = adapter.consume_debug_record()

    assert payload.decision == "continue"
    assert record is not None
    assert record["context"] == {"prompt": "hello"}
    assert "langfuse" in record
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_claude_roles.py::test_role_adapter_subprocess_env_includes_langfuse tests/test_claude_roles.py::test_role_adapter_records_debug_metadata_from_observation -v
```

Expected: FAIL because `_subprocess_env` does not include Langfuse variables and debug records do not include `langfuse`.

- [ ] **Step 3: Implement Claude role telemetry**

Modify imports near the top of `studio/llm/claude_roles.py`:

```python
from studio.observability import LangfuseTelemetry
```

In `ClaudeRoleAdapter.__init__`, add:

```python
self._telemetry = LangfuseTelemetry.from_project_root(self.project_root)
```

In `generate`, wrap the existing body after `prompt = self._prompt(...)`:

```python
metadata = {
    "role_name": role_name,
    "session_id": self.session_id,
    "resume_session": self.resume_session,
    "claude_project_root": str(self._claude_project_root()),
}
with self._telemetry.llm_observation(
    name=f"claude:{role_name}",
    metadata=metadata,
    input={"prompt": prompt, "context": context},
) as observation:
    try:
        config = self.load_config()
        observation.update(metadata={"model": config.model, "mode": config.mode})
        if not config.enabled:
            raise ClaudeRoleError("claude_disabled")
        if not config.api_key:
            raise ClaudeRoleError("missing_claude_configuration")

        if self._has_running_loop():
            payload = self._generate_payload_via_subprocess(role_name, context, prompt)
        else:
            try:
                payload = asyncio.run(self._generate_payload(role_name, context, config, prompt))
            except ClaudeRoleError as exc:
                if "Blocking call to os.getcwd" not in str(exc):
                    raise
                payload = self._generate_payload_via_subprocess(role_name, context, prompt)
        observation.update(output=payload)
        if self._last_debug_record is not None:
            self._last_debug_record["langfuse"] = self._telemetry.current_metadata()
        return payload
    except Exception as exc:
        observation.update(error=exc)
        raise
```

Apply the same pattern in `chat`, using:

```python
with self._telemetry.llm_observation(
    name="claude:chat",
    metadata={
        "role_name": "chat",
        "session_id": self.session_id,
        "resume_session": self.resume_session,
        "claude_project_root": str(self._claude_project_root()),
    },
    input={"message": message},
) as observation:
    ...
    observation.update(output=reply)
```

Modify `_subprocess_env` at the end:

```python
env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
return self._telemetry.subprocess_env(env)
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
uv run pytest tests/test_claude_roles.py::test_role_adapter_subprocess_env_includes_langfuse tests/test_claude_roles.py::test_role_adapter_records_debug_metadata_from_observation -v
```

Expected: PASS.

- [ ] **Step 5: Run full Claude role tests**

Run:

```powershell
uv run pytest tests/test_claude_roles.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add studio/llm/claude_roles.py tests/test_claude_roles.py
git commit -m "Instrument Claude role adapter with Langfuse telemetry"
```

Expected: commit succeeds.

## Task 5: Claude Worker Adapter Instrumentation

**Files:**
- Modify: `studio/llm/claude_worker.py`
- Test: `tests/test_claude_worker.py`

- [ ] **Step 1: Add failing subprocess env test**

Append to `tests/test_claude_worker.py`:

```python
def test_worker_adapter_subprocess_env_includes_langfuse(tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "worker"
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
    profile = _profile(system_prompt="worker", claude_project_root=claude_root)
    adapter = claude_worker_module.ClaudeWorkerAdapter(project_root=tmp_path, profile=profile)

    env = adapter._subprocess_env()

    assert env["LANGFUSE_PUBLIC_KEY"] == "pk"
    assert env["LANGFUSE_SECRET_KEY"] == "sk"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_claude_worker.py::test_worker_adapter_subprocess_env_includes_langfuse -v
```

Expected: FAIL because worker subprocess env lacks Langfuse variables.

- [ ] **Step 3: Implement worker telemetry**

Modify imports in `studio/llm/claude_worker.py`:

```python
from studio.observability import LangfuseTelemetry
```

In `ClaudeWorkerAdapter.__init__`, add:

```python
self._telemetry = LangfuseTelemetry.from_project_root(self.project_root)
```

Wrap `generate_design_brief` after role-adapter handling starts:

```python
with self._telemetry.llm_observation(
    name="claude:worker",
    metadata={"role_name": "worker"},
    input={"prompt": prompt},
) as observation:
    try:
        if self._role_adapter is not None:
            payload = self._role_adapter.generate("worker", {"prompt": prompt})
            if hasattr(self._role_adapter, "consume_debug_record"):
                self._last_debug_record = self._role_adapter.consume_debug_record()
            coerced = _coerce_payload(payload)
            observation.update(output=coerced)
            return coerced

        config = self.load_config()
        observation.update(metadata={"model": config.model, "mode": config.mode})
        if not config.enabled:
            raise ClaudeWorkerError("claude_disabled")
        if not config.api_key:
            raise ClaudeWorkerError("missing_claude_configuration")
        if self._has_running_loop():
            payload = self._generate_design_brief_via_subprocess(prompt)
        else:
            try:
                payload = asyncio.run(self._generate_design_brief(prompt, config))
            except ClaudeWorkerError as exc:
                if "Blocking call to os.getcwd" not in str(exc):
                    raise
                payload = self._generate_design_brief_via_subprocess(prompt)
        observation.update(output=payload)
        if self._last_debug_record is not None:
            self._last_debug_record["langfuse"] = self._telemetry.current_metadata()
        return payload
    except Exception as exc:
        observation.update(error=exc)
        raise
```

Modify `_subprocess_env` at the end:

```python
env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
return self._telemetry.subprocess_env(env)
```

- [ ] **Step 4: Run targeted test**

Run:

```powershell
uv run pytest tests/test_claude_worker.py::test_worker_adapter_subprocess_env_includes_langfuse -v
```

Expected: PASS.

- [ ] **Step 5: Run full worker tests**

Run:

```powershell
uv run pytest tests/test_claude_worker.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add studio/llm/claude_worker.py tests/test_claude_worker.py
git commit -m "Instrument Claude worker adapter with Langfuse telemetry"
```

Expected: commit succeeds.

## Task 6: Local LLM Log Metadata Enrichment

**Files:**
- Modify: `studio/runtime/llm_logs.py`
- Test: create or modify `tests/test_llm_logs.py`

- [ ] **Step 1: Add failing test for optional metadata**

Create `tests/test_llm_logs.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from studio.runtime.llm_logs import LlmRunLogger


def test_llm_logger_persists_optional_langfuse_metadata(tmp_path: Path) -> None:
    logger = LlmRunLogger(tmp_path)

    logger.append(
        run_id="run-1",
        node_name="worker",
        prompt="prompt",
        context={"safe": True},
        reply={"ok": True},
        metadata={
            "langfuse_trace_id": "trace-1",
            "langfuse_observation_id": "obs-1",
            "langfuse_url": "https://langfuse.example/project/traces/trace-1",
        },
    )

    entries = json.loads((tmp_path / "run-1.json").read_text(encoding="utf-8"))

    assert entries[0]["metadata"]["langfuse_trace_id"] == "trace-1"
    assert entries[0]["metadata"]["langfuse_observation_id"] == "obs-1"
    assert entries[0]["metadata"]["langfuse_url"].endswith("/trace-1")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_llm_logs.py -v
```

Expected: FAIL because `LlmRunLogger.append` does not accept `metadata`.

- [ ] **Step 3: Add metadata parameter**

Modify `LlmRunLogger.append` signature in `studio/runtime/llm_logs.py`:

```python
def append(
    self,
    *,
    run_id: str,
    node_name: str,
    prompt: str,
    context: dict[str, object],
    reply: Any,
    metadata: dict[str, object] | None = None,
) -> None:
```

Add `metadata` to the payload:

```python
payload = {
    "timestamp": datetime.now(UTC).isoformat(),
    "run_id": run_id,
    "node_name": node_name,
    "prompt": _json_ready(prompt),
    "context": _json_ready(context),
    "reply": _json_ready(reply),
}
if metadata:
    payload["metadata"] = _json_ready(metadata)
```

- [ ] **Step 4: Run test**

Run:

```powershell
uv run pytest tests/test_llm_logs.py -v
```

Expected: PASS.

- [ ] **Step 5: Run existing log-related tests**

Run:

```powershell
uv run pytest tests/api/test_meeting_transcript.py tests/api/test_logs.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add studio/runtime/llm_logs.py tests/test_llm_logs.py
git commit -m "Allow LLM logs to store Langfuse metadata"
```

Expected: commit succeeds.

## Task 7: Graph Node Span Instrumentation

**Files:**
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_graph_run.py`, `tests/test_meeting_graph.py`, `tests/test_session_meeting_graph.py`

- [ ] **Step 1: Add failing test for telemetry no-op graph execution**

Append to `tests/test_graph_run.py`:

```python
def test_demo_graph_runs_with_langfuse_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONUTF8", "1")
    graph = build_demo_runtime(tmp_path)

    result = graph.invoke({"prompt": "Design a tiny puzzle game"})

    assert result["telemetry"]["status"] == "completed"
    assert "node_traces" in result["telemetry"]
```

If `tests/test_graph_run.py` already has equivalent imports, reuse them. The required imports are:

```python
from pathlib import Path

import pytest

from studio.runtime.graph import build_demo_runtime
```

- [ ] **Step 2: Run test before instrumentation**

Run:

```powershell
uv run pytest tests/test_graph_run.py::test_demo_graph_runs_with_langfuse_disabled -v
```

Expected: PASS. This is a guard test: graph behavior must stay unchanged before and after instrumentation.

- [ ] **Step 3: Import telemetry in graph module**

Add to `studio/runtime/graph.py` imports:

```python
from studio.observability import LangfuseTelemetry
```

- [ ] **Step 4: Instrument demo graph**

Inside `build_demo_runtime`, after `llm_logs = LlmRunLogger(root / "logs")`, add:

```python
telemetry = LangfuseTelemetry.from_project_root(Path.cwd())
```

Wrap each node body with a node span. For `worker_node`, use this pattern:

```python
def worker_node(state: dict[str, Any]) -> dict[str, Any]:
    runtime_state = RuntimeState.model_validate(state)
    run_id = runtime_state.run_id
    with telemetry.node_span(
        name="worker",
        metadata={
            "graph": "game_studio_demo",
            "run_id": run_id,
            "task_id": f"{run_id}-worker",
            "node_name": "worker",
        },
        input={"goal": runtime_state.goal},
    ) as span:
        session_tag = _session_tag_for_run(run_id)
        runtime_state = runtime_state.model_copy(update={"task_id": f"{run_id}-worker"})
        agent = dispatcher.get("worker")
        result = agent.run(runtime_state)
        llm_entry = _consume_agent_llm_log(agent)
        if llm_entry is not None:
            llm_logs.append(
                run_id=run_id,
                node_name="worker",
                metadata=telemetry.current_metadata(),
                **llm_entry,
            )
        stored = []
        for artifact in result.artifacts:
            unique_id = f"{artifact.artifact_id}-{session_tag}"
            to_store = artifact.model_copy(update={"artifact_id": unique_id})
            stored.append(artifact_registry.save(to_store))
        memory_key = f"{run_id}-summary"
        memory_store.put("run", memory_key, {"summary": "worker produced concept draft"})
        merged = _merge_runtime_state(
            runtime_state,
            state_patch=result.state_patch,
            node_name="worker",
            trace=result.trace,
            overrides={"artifacts": stored},
        )
        checkpoints.save(_checkpoint_key(run_id, "worker"), merged)
        span.update(
            metadata={
                "fallback_used": bool(result.trace.get("fallback_used", False)),
                "fallback_reason": str(result.trace.get("fallback_reason", "")),
            },
            output={"status": merged.telemetry.get("status"), "artifact_count": len(stored)},
        )
        return merged.model_dump(mode="json")
```

Apply the same shape to `planner_node` and `reviewer_node`. For `planner_node`, create `run_id` before entering the span. For `reviewer_node`, include `decision` and `status`.

- [ ] **Step 5: Instrument design, delivery, and meeting graph nodes**

For each node function in `build_design_graph`, `build_delivery_graph`, and `build_meeting_graph`, instantiate telemetry inside the builder:

```python
telemetry = LangfuseTelemetry.from_project_root(Path.cwd())
```

Wrap the node body:

```python
with telemetry.node_span(
    name="moderator_prepare",
    metadata={
        "graph": "studio_meeting_workflow",
        "requirement_id": requirement_id,
        "node_name": "moderator_prepare",
        "agent_role": "moderator",
    },
    input={"user_intent": user_intent, "meeting_context": meeting_context},
) as span:
    ...
    span.update(output={"attendees": filtered, "agenda_count": len(prep.get("agenda", []))})
    return {...}
```

Use these graph names:

```python
"studio_design_workflow"
"studio_delivery_workflow"
"studio_meeting_workflow"
```

Use concise outputs such as counts, status, fallback flags, and ids.

- [ ] **Step 6: Run graph tests**

Run:

```powershell
uv run pytest tests/test_graph_run.py tests/test_meeting_graph.py tests/test_session_meeting_graph.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add studio/runtime/graph.py tests/test_graph_run.py
git commit -m "Add Langfuse spans to runtime graphs"
```

Expected: commit succeeds.

## Task 8: README Documentation

**Files:**
- Modify: `README.md`
- Test: none

- [ ] **Step 1: Add Langfuse section**

Add this section after the existing LangGraph Studio observability notes:

````markdown
### Optional Langfuse Observability

Game Studio can export workflow and LLM traces to Langfuse. This is optional;
local development and tests run without Langfuse credentials.

Start from `.env.example`:

```env
GAME_STUDIO_LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
GAME_STUDIO_LANGFUSE_CAPTURE_IO=true
GAME_STUDIO_LANGFUSE_SAMPLE_RATE=1.0
```

To enable Langfuse:

1. Set `GAME_STUDIO_LANGFUSE_ENABLED=true`.
2. Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.
3. Keep `LANGFUSE_HOST=https://cloud.langfuse.com` for Langfuse Cloud, or set your self-hosted URL.
4. Run a CLI or Web workflow.

Manual smoke test:

```batch
uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

Langfuse should show workflow spans and Claude observations. Local `llm_logs`
continue to be written for offline debugging.
````

- [ ] **Step 2: Review README diff**

Run:

```powershell
git diff -- README.md
```

Expected: new Langfuse documentation only.

- [ ] **Step 3: Commit**

Run:

```powershell
git add README.md
git commit -m "Document Langfuse observability setup"
```

Expected: commit succeeds.

## Task 9: Final Verification

**Files:**
- No new source files unless verification reveals a defect.

- [ ] **Step 1: Run focused backend test suite**

Run:

```powershell
uv run pytest tests/test_langfuse_observability.py tests/test_claude_roles.py tests/test_claude_worker.py tests/test_llm_logs.py tests/test_graph_run.py tests/test_meeting_graph.py tests/test_session_meeting_graph.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full Python tests**

Run:

```powershell
uv run pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run no-credential manual smoke test**

Run:

```powershell
uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

Expected: command completes with the same behavior as before Langfuse integration.

- [ ] **Step 4: Inspect local logs**

Run:

```powershell
Get-ChildItem .runtime-data -Recurse -Filter *.json | Select-Object -First 10 FullName
```

Expected: local JSON logs are still created. When Langfuse is disabled, Langfuse metadata may be absent.

- [ ] **Step 5: Review final diff**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: working tree contains no uncommitted changes from this implementation. Pre-existing unrelated changes may still be present if they were present before execution.

## Self-Review Notes

- Spec coverage: dependency/config, no-op mode, graph spans, Claude role/worker observations, subprocess env propagation, local log enrichment, docs, redaction, truncation, and tests are each covered by a task.
- Scope: this plan implements backend observability only. It does not build a frontend dashboard or change workflow behavior.
- Type consistency: `LangfuseTelemetry`, `LangfuseConfig`, `graph_trace`, `node_span`, `llm_observation`, `subprocess_env`, `current_metadata`, and `redact` are introduced before use in later tasks.
