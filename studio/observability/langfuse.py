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
_DEFAULT_BACKEND = object()


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
            if _is_sensitive_key(key_str):
                redacted[key_str] = "[REDACTED]"
            else:
                redacted[key_str] = redact(item, max_string_length=max_string_length)
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
        return cls(
            enabled=_parse_bool(values.get("GAME_STUDIO_LANGFUSE_ENABLED"), default=False),
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
        langfuse_observation: Any = None,
    ) -> None:
        self.telemetry = telemetry
        self.kind = kind
        self.name = name
        self.metadata = redact(metadata or {})
        self.input = redact(input) if telemetry.config.capture_io else None
        self.output: Any = None
        self.error: str | None = None
        self._langfuse_observation = langfuse_observation

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
        self.telemetry._update_backend(self)
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
        backend: Any = _DEFAULT_BACKEND,
        record_events: bool = False,
    ) -> None:
        self.config = config or LangfuseConfig()
        self.backend = self._load_backend() if backend is _DEFAULT_BACKEND else backend
        self.events: list[dict[str, Any]] = []
        self._record_events = record_events

    @property
    def enabled(self) -> bool:
        return self.config.export_enabled

    @classmethod
    def from_project_root(cls, project_root: Path) -> "LangfuseTelemetry":
        return cls(config=LangfuseConfig.from_env(project_root))

    @classmethod
    def fake(cls) -> "LangfuseTelemetry":
        return cls(
            config=LangfuseConfig(enabled=True, public_key="pk", secret_key="sk"),
            backend=None,
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
        with self._observation_context(
            kind="trace",
            name=name,
            as_type="span",
            metadata=metadata,
            input=input,
        ) as observation:
            yield observation

    @contextmanager
    def node_span(
        self,
        *,
        name: str,
        metadata: dict[str, object],
        input: Any = None,
    ) -> Iterator[_Observation]:
        with self._observation_context(
            kind="span",
            name=name,
            as_type="span",
            metadata=metadata,
            input=input,
        ) as observation:
            yield observation

    @contextmanager
    def llm_observation(
        self,
        *,
        name: str,
        metadata: dict[str, object],
        input: Any = None,
    ) -> Iterator[_Observation]:
        with self._observation_context(
            kind="generation",
            name=name,
            as_type="generation",
            metadata=metadata,
            input=input,
        ) as observation:
            yield observation

    def subprocess_env(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(base_env or os.environ)
        if not self.config.export_enabled:
            return env
        env["GAME_STUDIO_LANGFUSE_ENABLED"] = "true"
        env["LANGFUSE_PUBLIC_KEY"] = self.config.public_key or ""
        env["LANGFUSE_SECRET_KEY"] = self.config.secret_key or ""
        env["LANGFUSE_HOST"] = self.config.host
        return env

    @contextmanager
    def _observation_context(
        self,
        *,
        kind: str,
        name: str,
        as_type: str,
        metadata: dict[str, object],
        input: Any,
    ) -> Iterator[_Observation]:
        redacted_metadata = redact(metadata)
        redacted_input = redact(input) if self.config.capture_io else None
        backend_context = self._start_backend_context(
            name=name,
            as_type=as_type,
            metadata=redacted_metadata,
            input=redacted_input,
        )
        token = _CURRENT_METADATA.set({**self.current_metadata(), **redacted_metadata})
        event_prefix = "generation" if kind == "generation" else kind
        self._record(f"{event_prefix}_start", name, metadata=redacted_metadata, input=redacted_input)
        try:
            if backend_context is None:
                observation = _Observation(
                    self,
                    kind=kind,
                    name=name,
                    metadata=redacted_metadata,
                    input=redacted_input,
                )
                yield observation
            else:
                with backend_context as backend_observation:
                    observation = _Observation(
                        self,
                        kind=kind,
                        name=name,
                        metadata=redacted_metadata,
                        input=redacted_input,
                        langfuse_observation=backend_observation,
                    )
                    yield observation
        except Exception as exc:
            observation.update(error=exc)
            raise
        finally:
            self._record(
                f"{event_prefix}_end",
                name,
                metadata=observation.metadata,
                output=observation.output,
                error=observation.error,
            )
            _CURRENT_METADATA.reset(token)

    def _load_backend(self) -> Any | None:
        if not self.config.export_enabled:
            return None
        self._apply_env()
        try:
            from langfuse import get_client

            return get_client()
        except Exception:
            return None

    def _apply_env(self) -> None:
        if not self.config.export_enabled:
            return
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", self.config.public_key or "")
        os.environ.setdefault("LANGFUSE_SECRET_KEY", self.config.secret_key or "")
        os.environ.setdefault("LANGFUSE_HOST", self.config.host)

    def _start_backend_context(
        self,
        *,
        name: str,
        as_type: str,
        metadata: Any,
        input: Any,
    ) -> Any | None:
        if self.backend is None or not self.config.export_enabled:
            return None
        start = getattr(self.backend, "start_as_current_observation", None)
        if not callable(start):
            return None
        try:
            return start(
                name=name,
                as_type=as_type,
                metadata=metadata,
                input=input,
                end_on_exit=True,
            )
        except Exception:
            return None

    def _update_backend(self, observation: _Observation) -> None:
        if observation._langfuse_observation is None:
            return
        update = getattr(observation._langfuse_observation, "update", None)
        if not callable(update):
            return
        kwargs: dict[str, Any] = {
            "metadata": observation.metadata,
        }
        if observation.output is not None:
            kwargs["output"] = observation.output
        if observation.error is not None:
            kwargs["level"] = "ERROR"
            kwargs["status_message"] = observation.error
        try:
            update(**kwargs)
        except Exception:
            return

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
