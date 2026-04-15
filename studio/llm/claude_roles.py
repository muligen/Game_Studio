from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import ResultMessage
from pydantic import BaseModel, ConfigDict, ValidationError

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off", ""}


class ClaudeRoleError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaudeRoleConfig:
    enabled: bool
    mode: str
    model: str | None
    api_key: str | None
    base_url: str | None


class ReviewerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["continue", "stop"]
    reason: str
    risks: list[str]


class DesignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    core_rules: list[str]
    acceptance_criteria: list[str]
    open_questions: list[str]


class DevPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    changes: list[str]
    checks: list[str]
    follow_ups: list[str]


class QaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    passed: bool
    suggested_bug: str | None


class QualityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    ready: bool
    risks: list[str]
    follow_ups: list[str]


class ArtPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    style_direction: str
    asset_list: list[str]


_ROLE_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "art": ArtPayload,
    "dev": DevPayload,
    "design": DesignPayload,
    "qa": QaPayload,
    "quality": QualityPayload,
    "reviewer": ReviewerPayload,
}

_ROLE_OUTPUT_FORMATS: dict[str, dict[str, object]] = {
    "art": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "style_direction": {"type": "string"},
            "asset_list": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "style_direction", "asset_list"],
        "additionalProperties": False,
    },
    "dev": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "changes": {"type": "array", "items": {"type": "string"}},
            "checks": {"type": "array", "items": {"type": "string"}},
            "follow_ups": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "changes", "checks", "follow_ups"],
        "additionalProperties": False,
    },
    "design": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "core_rules": {"type": "array", "items": {"type": "string"}},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "summary",
            "core_rules",
            "acceptance_criteria",
            "open_questions",
        ],
        "additionalProperties": False,
    },
    "reviewer": {
        "type": "object",
        "properties": {
            "decision": {"type": "string"},
            "reason": {"type": "string"},
            "risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["decision", "reason", "risks"],
        "additionalProperties": False,
    },
    "qa": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "passed": {"type": "boolean"},
            "suggested_bug": {"type": ["string", "null"]},
        },
        "required": ["summary", "passed", "suggested_bug"],
        "additionalProperties": False,
    },
    "quality": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "ready": {"type": "boolean"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "follow_ups": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "ready", "risks", "follow_ups"],
        "additionalProperties": False,
    },
}

_ROLE_PROMPTS: dict[str, str] = {
    "art": (
        "You are the art role.\n"
        "Return only JSON with summary, style_direction, and asset_list.\n"
        "summary and style_direction must be concise strings.\n"
        "asset_list must be a list of concrete strings.\n"
    ),
    "dev": (
        "You are the dev role.\n"
        "Return only JSON with summary, changes, checks, and follow_ups.\n"
        "summary must be a concise string.\n"
        "changes, checks, and follow_ups must be lists of concrete strings.\n"
    ),
    "design": (
        "You are the design role.\n"
        "Return only JSON with title, summary, core_rules, acceptance_criteria, and open_questions.\n"
        "title and summary must be concise strings.\n"
        "core_rules, acceptance_criteria, and open_questions must be lists of concrete strings.\n"
    ),
    "reviewer": (
        "You are the reviewer role.\n"
        "Return only JSON with decision, reason, and risks.\n"
        "decision must be continue or stop.\n"
        "reason must explain the choice.\n"
        "risks must be a list of concrete issues.\n"
    ),
    "qa": (
        "You are the qa role.\n"
        "Return only JSON with summary, passed, and suggested_bug.\n"
        "summary must be a concise string.\n"
        "passed must be a boolean.\n"
        "suggested_bug must be either a concise string or null.\n"
    ),
    "quality": (
        "You are the quality role.\n"
        "Return only JSON with summary, ready, risks, and follow_ups.\n"
        "summary must be a concise string.\n"
        "ready must be a boolean.\n"
        "risks and follow_ups must be lists of concrete strings.\n"
    ),
}

_ACTIVE_ROLE_NAMES = set(_ROLE_PAYLOAD_MODELS)


def parse_role_payload(
    role_name: str, data: object
) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload:
    model = _ROLE_PAYLOAD_MODELS.get(role_name)
    if model is None:
        raise ClaudeRoleError("invalid_claude_output")
    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        raise ClaudeRoleError("invalid_claude_output") from exc
    if isinstance(parsed, (ReviewerPayload, DesignPayload, DevPayload, QaPayload, QualityPayload, ArtPayload)):
        return parsed
    raise ClaudeRoleError("invalid_claude_output")


def _repo_root_from(path: Path | None) -> Path:
    if path is not None:
        return path
    return Path(__file__).resolve().parents[2]


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
    raise ClaudeRoleError(f"invalid_boolean:{value}")


def _require_active_role(role_name: str) -> None:
    if role_name not in _ACTIVE_ROLE_NAMES:
        raise ClaudeRoleError(f"unsupported_role:{role_name}")


class ClaudeRoleAdapter:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = _repo_root_from(project_root)
        self._env_path = self.project_root / ".env"

    def load_config(self) -> ClaudeRoleConfig:
        values = _parse_dotenv(self._env_path)
        enabled = _parse_bool(values.get("GAME_STUDIO_CLAUDE_ENABLED"), default=False)
        mode = values.get("GAME_STUDIO_CLAUDE_MODE", "text").strip() or "text"
        if mode not in {"text", "tools_enabled"}:
            raise ClaudeRoleError(f"invalid_mode:{mode}")

        return ClaudeRoleConfig(
            enabled=enabled,
            mode=mode,
            model=values.get("GAME_STUDIO_CLAUDE_MODEL") or None,
            api_key=values.get("ANTHROPIC_API_KEY") or None,
            base_url=values.get("ANTHROPIC_BASE_URL") or None,
        )

    def generate(
        self, role_name: str, context: dict[str, object]
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload:
        _require_active_role(role_name)

        config = self.load_config()
        if not config.enabled:
            raise ClaudeRoleError("claude_disabled")
        if not config.api_key:
            raise ClaudeRoleError("missing_claude_configuration")

        if self._has_running_loop():
            return self._generate_payload_via_subprocess(role_name, context)

        try:
            return asyncio.run(self._generate_payload(role_name, context, config))
        except ClaudeRoleError as exc:
            if "Blocking call to os.getcwd" not in str(exc):
                raise
            return self._generate_payload_via_subprocess(role_name, context)

    @staticmethod
    def _has_running_loop() -> bool:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return False
        return True

    async def _generate_payload(
        self,
        role_name: str,
        context: dict[str, object],
        config: ClaudeRoleConfig,
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload:
        options = ClaudeAgentOptions(
            cwd=self.project_root,
            model=config.model,
            tools=[] if config.mode == "text" else None,
            permission_mode="default",
            setting_sources=["project"],
            env=self._sdk_env(config),
            output_format=self._output_format(role_name),
        )

        result: ResultMessage | None = None
        try:
            async for message in query(prompt=self._prompt(role_name, context), options=options):
                if isinstance(message, ResultMessage):
                    result = message
        except Exception as exc:  # pragma: no cover - exercised via fallback tests
            raise ClaudeRoleError(str(exc) or exc.__class__.__name__) from exc

        if result is None:
            raise ClaudeRoleError("missing_claude_result")
        if result.is_error:
            message = "; ".join(result.errors or []) or result.result or "claude_run_failed"
            raise ClaudeRoleError(message)

        payload: Any
        if result.structured_output is not None:
            payload = result.structured_output
        elif result.result is not None:
            try:
                payload = json.loads(result.result)
            except json.JSONDecodeError as exc:
                raise ClaudeRoleError("invalid_claude_output") from exc
        else:
            raise ClaudeRoleError("invalid_claude_output")

        return parse_role_payload(role_name, payload)

    def _sdk_env(self, config: ClaudeRoleConfig) -> dict[str, str]:
        env = {"ANTHROPIC_API_KEY": config.api_key or ""}
        if config.base_url:
            env["ANTHROPIC_BASE_URL"] = config.base_url
        return env

    def _generate_payload_via_subprocess(
        self,
        role_name: str,
        context: dict[str, object],
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload:
        _require_active_role(role_name)
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "studio.llm.claude_roles",
                    "--project-root",
                    str(self.project_root),
                    "--role-name",
                    role_name,
                ],
                cwd=self.project_root,
                input=json.dumps(context, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ClaudeRoleError(str(exc) or "claude_subprocess_failed") from exc
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "claude_subprocess_failed"
            raise ClaudeRoleError(message)

        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeRoleError("invalid_claude_output") from exc
        return parse_role_payload(role_name, parsed)

    @staticmethod
    def _prompt(role_name: str, context: dict[str, object]) -> str:
        payload = json.dumps(context, ensure_ascii=False, sort_keys=True)
        prompt = _ROLE_PROMPTS.get(role_name)
        if prompt is not None:
            return f"{prompt}Context: {payload}"
        return (
            f"You are the {role_name} role.\n"
            "Return only JSON.\n"
            f"Context: {payload}"
        )

    @staticmethod
    def _output_format(role_name: str) -> dict[str, object]:
        output_format = _ROLE_OUTPUT_FORMATS.get(role_name)
        if output_format is not None:
            return output_format
        if role_name in _ACTIVE_ROLE_NAMES:
            raise ClaudeRoleError(f"missing_output_format:{role_name}")
        return _ROLE_OUTPUT_FORMATS["reviewer"]


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--role-name", required=True)
    args = parser.parse_args()
    _require_active_role(args.role_name)

    adapter = ClaudeRoleAdapter(project_root=Path(args.project_root))
    config = adapter.load_config()
    if not config.enabled:
        raise ClaudeRoleError("claude_disabled")
    if not config.api_key:
        raise ClaudeRoleError("missing_claude_configuration")

    payload = asyncio.run(
        adapter._generate_payload(
            args.role_name,
            json.loads(sys.stdin.read()),
            config,
        )
    )
    print(payload.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
