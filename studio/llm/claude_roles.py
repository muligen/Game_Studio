from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import ResultMessage
from pydantic import BaseModel, ConfigDict, ValidationError

from studio.agents.profile_schema import AgentProfile

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


class WorkerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    genre: str


_ROLE_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "art": ArtPayload,
    "dev": DevPayload,
    "design": DesignPayload,
    "qa": QaPayload,
    "quality": QualityPayload,
    "reviewer": ReviewerPayload,
    "worker": WorkerPayload,
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
    "worker": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "genre": {"type": "string"},
        },
        "required": ["title", "summary", "genre"],
        "additionalProperties": False,
    },
}

_ACTIVE_ROLE_NAMES = set(_ROLE_PAYLOAD_MODELS)


def parse_role_payload(
    role_name: str, data: object
) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload | WorkerPayload:
    model = _ROLE_PAYLOAD_MODELS.get(role_name)
    if model is None:
        raise ClaudeRoleError("invalid_claude_output")
    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        raise ClaudeRoleError("invalid_claude_output") from exc
    if isinstance(
        parsed,
        (ReviewerPayload, DesignPayload, DevPayload, QaPayload, QualityPayload, ArtPayload, WorkerPayload),
    ):
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
    def __init__(
        self,
        project_root: Path | None = None,
        profile: AgentProfile | None = None,
    ) -> None:
        self.project_root = _repo_root_from(project_root)
        self.profile = profile
        self._env_path = self.project_root / ".env"
        self._last_debug_record: dict[str, object] | None = None

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
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload | WorkerPayload:
        _require_active_role(role_name)
        prompt = self._prompt(role_name, context)

        config = self.load_config()
        if not config.enabled:
            raise ClaudeRoleError("claude_disabled")
        if not config.api_key:
            raise ClaudeRoleError("missing_claude_configuration")

        if self._has_running_loop():
            return self._generate_payload_via_subprocess(role_name, context, prompt)

        try:
            return asyncio.run(self._generate_payload(role_name, context, config, prompt))
        except ClaudeRoleError as exc:
            if "Blocking call to os.getcwd" not in str(exc):
                raise
            return self._generate_payload_via_subprocess(role_name, context, prompt)

    def debug_prompt(self, role_name: str, context: dict[str, object]) -> str:
        _require_active_role(role_name)
        return self._prompt(role_name, context)

    def consume_debug_record(self) -> dict[str, object] | None:
        record = self._last_debug_record
        self._last_debug_record = None
        return record

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
        prompt: str,
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload | WorkerPayload:
        options = ClaudeAgentOptions(
            cwd=self._claude_project_root(),
            model=config.model,
            tools=[] if config.mode == "text" else None,
            permission_mode="default",
            setting_sources=["project"],
            env=self._sdk_env(config),
            output_format=self._output_format(role_name),
        )

        result: ResultMessage | None = None
        try:
            async for message in query(prompt=prompt, options=options):
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
            reply: Any = result.structured_output
        elif result.result is not None:
            try:
                payload = self._parse_result_text(result.result)
            except (json.JSONDecodeError, ClaudeRoleError) as exc:
                raise ClaudeRoleError("invalid_claude_output") from exc
            reply = result.result
        else:
            raise ClaudeRoleError("invalid_claude_output")

        self._last_debug_record = {
            "prompt": prompt,
            "context": context,
            "reply": reply,
        }
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
        prompt: str,
    ) -> ReviewerPayload | DesignPayload | DevPayload | QaPayload | QualityPayload | ArtPayload | WorkerPayload:
        _require_active_role(role_name)
        script_path = Path(__file__).resolve()
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--project-root",
                    str(self.project_root),
                    "--claude-project-root",
                    str(self._claude_project_root()),
                    "--system-prompt",
                    self._require_profile().system_prompt,
                    "--role-name",
                    role_name,
                ],
                cwd=self._claude_project_root(),
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
        self._last_debug_record = {
            "prompt": prompt,
            "context": context,
            "reply": proc.stdout,
        }
        return parse_role_payload(role_name, parsed)

    def _prompt(self, role_name: str, context: dict[str, object]) -> str:
        payload = json.dumps(context, ensure_ascii=False, sort_keys=True)
        return "\n".join(
            [
                self._require_profile().system_prompt,
                "Return only JSON matching this schema:",
                json.dumps(self._output_format(role_name), ensure_ascii=False, sort_keys=True),
                f"Context: {payload}",
            ]
        )

    def _require_profile(self) -> AgentProfile:
        if self.profile is None:
            raise ClaudeRoleError("missing_agent_profile")
        return self.profile

    def _claude_project_root(self) -> Path:
        return self._require_profile().claude_project_root

    @staticmethod
    def _output_format(role_name: str) -> dict[str, object]:
        output_format = _ROLE_OUTPUT_FORMATS.get(role_name)
        if output_format is not None:
            return output_format
        if role_name in _ACTIVE_ROLE_NAMES:
            raise ClaudeRoleError(f"missing_output_format:{role_name}")
        return _ROLE_OUTPUT_FORMATS["reviewer"]

    @staticmethod
    def _parse_result_text(result_text: str) -> dict[str, Any]:
        candidates = [result_text.strip()]
        fenced = ClaudeRoleAdapter._extract_fenced_block(result_text)
        if fenced is not None and fenced not in candidates:
            candidates.append(fenced)

        embedded = ClaudeRoleAdapter._extract_json_object(result_text)
        if embedded is not None and embedded not in candidates:
            candidates.append(embedded)

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        raise ClaudeRoleError("invalid_claude_output")

    @staticmethod
    def _extract_fenced_block(text: str) -> str | None:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match is None:
            return None
        return match.group(1).strip()

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        decoder = json.JSONDecoder()
        for start_index, char in enumerate(text):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[start_index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return text[start_index : start_index + len(json.dumps(payload, ensure_ascii=False))]
        return None


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--role-name", required=True)
    parser.add_argument("--system-prompt")
    parser.add_argument("--claude-project-root")
    try:
        args = parser.parse_args()
        _require_active_role(args.role_name)

        profile = None
        if args.system_prompt and args.claude_project_root:
            profile = AgentProfile(
                name=args.role_name,
                system_prompt=args.system_prompt,
                claude_project_root=Path(args.claude_project_root),
            )

        adapter = ClaudeRoleAdapter(project_root=Path(args.project_root), profile=profile)
        config = adapter.load_config()
        if not config.enabled:
            raise ClaudeRoleError("claude_disabled")
        if not config.api_key:
            raise ClaudeRoleError("missing_claude_configuration")

        context = json.loads(sys.stdin.read())
        payload = asyncio.run(
            adapter._generate_payload(
                args.role_name,
                context,
                config,
                adapter._prompt(args.role_name, context),
            )
        )
    except (ClaudeRoleError, json.JSONDecodeError) as exc:
        print(str(exc) or exc.__class__.__name__, file=sys.stderr)
        return 1

    print(payload.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
