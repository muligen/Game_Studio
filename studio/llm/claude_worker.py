from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import ResultMessage
import yaml

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off", ""}


class ClaudeWorkerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaudeWorkerPayload:
    title: str
    summary: str
    genre: str


@dataclass(frozen=True)
class ClaudeWorkerConfig:
    enabled: bool
    mode: str
    model: str | None
    api_key: str | None
    base_url: str | None


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
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        values[key] = value
    return values


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSEY:
        return False
    raise ClaudeWorkerError(f"invalid_boolean:{value}")


def _validated_payload(data: Any) -> ClaudeWorkerPayload:
    if not isinstance(data, dict):
        raise ClaudeWorkerError("invalid_claude_output")

    title = data.get("title")
    summary = data.get("summary")
    genre = data.get("genre")
    if not all(isinstance(v, str) and v.strip() for v in (title, summary, genre)):
        raise ClaudeWorkerError("invalid_claude_output")

    return ClaudeWorkerPayload(
        title=title.strip(),
        summary=summary.strip(),
        genre=genre.strip(),
    )


def _coerce_payload(data: Any) -> ClaudeWorkerPayload:
    if isinstance(data, ClaudeWorkerPayload):
        return data
    if hasattr(data, "model_dump") and callable(data.model_dump):
        return _validated_payload(data.model_dump())
    if all(hasattr(data, field) for field in ("title", "summary", "genre")):
        return _validated_payload(
            {
                "title": getattr(data, "title"),
                "summary": getattr(data, "summary"),
                "genre": getattr(data, "genre"),
            }
        )
    return _validated_payload(data)


class ClaudeWorkerAdapter:
    def __init__(
        self,
        project_root: Path | None = None,
        role_adapter: Any | None = None,
    ) -> None:
        self.project_root = _repo_root_from(project_root)
        self._env_path = self.project_root / ".env"
        self._role_adapter = role_adapter
        self._last_debug_record: dict[str, object] | None = None

    def load_config(self) -> ClaudeWorkerConfig:
        values = _parse_dotenv(self._env_path)
        enabled = _parse_bool(values.get("GAME_STUDIO_CLAUDE_ENABLED"), default=False)
        mode = values.get("GAME_STUDIO_CLAUDE_MODE", "text").strip() or "text"
        if mode not in {"text", "tools_enabled"}:
            raise ClaudeWorkerError(f"invalid_mode:{mode}")
        model = values.get("GAME_STUDIO_CLAUDE_MODEL") or None
        api_key = values.get("ANTHROPIC_API_KEY") or None
        base_url = values.get("ANTHROPIC_BASE_URL") or None
        return ClaudeWorkerConfig(
            enabled=enabled,
            mode=mode,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    def is_enabled(self) -> bool:
        return self.load_config().enabled

    def generate_design_brief(self, prompt: str) -> ClaudeWorkerPayload:
        if self._role_adapter is not None:
            try:
                payload = self._role_adapter.generate("worker", {"prompt": prompt})
            except Exception as exc:
                raise ClaudeWorkerError(str(exc) or exc.__class__.__name__) from exc
            if hasattr(self._role_adapter, "consume_debug_record"):
                self._last_debug_record = self._role_adapter.consume_debug_record()
            return _coerce_payload(payload)

        config = self.load_config()
        if not config.enabled:
            raise ClaudeWorkerError("claude_disabled")
        if not config.api_key:
            raise ClaudeWorkerError("missing_claude_configuration")
        try:
            return asyncio.run(self._generate_design_brief(prompt, config))
        except ClaudeWorkerError as exc:
            if "Blocking call to os.getcwd" not in str(exc):
                raise
            return self._generate_design_brief_via_subprocess(prompt)

    def debug_prompt(self, prompt: str) -> str:
        return self._prompt(prompt)

    def consume_debug_record(self) -> dict[str, object] | None:
        record = self._last_debug_record
        self._last_debug_record = None
        return record

    async def _generate_design_brief(
        self, prompt: str, config: ClaudeWorkerConfig
    ) -> ClaudeWorkerPayload:
        options = ClaudeAgentOptions(
            cwd=self.project_root,
            model=config.model,
            tools=[] if config.mode == "text" else None,
            permission_mode="default",
            setting_sources=["project"],
            env=self._sdk_env(config),
            output_format={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "genre": {"type": "string"},
                },
                "required": ["title", "summary", "genre"],
                "additionalProperties": False,
            },
        )

        result: ResultMessage | None = None
        try:
            async for message in query(prompt=self._prompt(prompt), options=options):
                if isinstance(message, ResultMessage):
                    result = message
        except Exception as exc:  # pragma: no cover - exercised via worker fallback tests
            raise ClaudeWorkerError(str(exc) or exc.__class__.__name__) from exc

        if result is None:
            raise ClaudeWorkerError("missing_claude_result")
        if result.is_error:
            message = "; ".join(result.errors or []) or result.result or "claude_run_failed"
            raise ClaudeWorkerError(message)

        if result.structured_output is not None:
            self._last_debug_record = {
                "prompt": self._prompt(prompt),
                "context": {"prompt": prompt},
                "reply": result.structured_output,
            }
            return _validated_payload(result.structured_output)
        if result.result is None:
            raise ClaudeWorkerError("invalid_claude_output")
        self._last_debug_record = {
            "prompt": self._prompt(prompt),
            "context": {"prompt": prompt},
            "reply": result.result,
        }
        return self._parse_result_text(result.result)

    def _sdk_env(self, config: ClaudeWorkerConfig) -> dict[str, str]:
        env = {"ANTHROPIC_API_KEY": config.api_key or ""}
        if config.base_url:
            env["ANTHROPIC_BASE_URL"] = config.base_url
        return env

    def _generate_design_brief_via_subprocess(self, prompt: str) -> ClaudeWorkerPayload:
        cmd = [
            sys.executable,
            "-m",
            "studio.llm.claude_worker",
            "--project-root",
            str(self.project_root),
            "--prompt",
            prompt,
        ]
        proc = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        if proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip() or "claude_subprocess_failed"
            raise ClaudeWorkerError(message)
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeWorkerError("invalid_claude_output") from exc
        self._last_debug_record = {
            "prompt": self._prompt(prompt),
            "context": {"prompt": prompt},
            "reply": proc.stdout,
        }
        return _validated_payload(parsed)

    @staticmethod
    def _parse_result_text(result_text: str) -> ClaudeWorkerPayload:
        candidates = [result_text.strip()]
        fenced = ClaudeWorkerAdapter._extract_fenced_block(result_text)
        if fenced is not None and fenced not in candidates:
            candidates.insert(0, fenced)

        for candidate in candidates:
            try:
                return _validated_payload(json.loads(candidate))
            except (json.JSONDecodeError, ClaudeWorkerError, TypeError):
                pass

            try:
                parsed_yaml = yaml.safe_load(candidate)
            except yaml.YAMLError:
                continue
            try:
                return _validated_payload(parsed_yaml)
            except ClaudeWorkerError:
                continue

        raise ClaudeWorkerError("invalid_claude_output")

    @staticmethod
    def _extract_fenced_block(text: str) -> str | None:
        match = re.search(r"```(?:json|yaml|yml)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match is None:
            return None
        return match.group(1).strip()

    @staticmethod
    def _prompt(user_prompt: str) -> str:
        return (
            "You are generating a compact game design brief.\n"
            "Return only an object with the keys title, summary, and genre.\n"
            "Do not add markdown fences, explanations, or extra keys.\n"
            f"User prompt: {user_prompt}"
        )


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    adapter = ClaudeWorkerAdapter(project_root=Path(args.project_root))
    config = adapter.load_config()
    if not config.enabled:
        raise ClaudeWorkerError("claude_disabled")
    if not config.api_key:
        raise ClaudeWorkerError("missing_claude_configuration")

    payload = asyncio.run(adapter._generate_design_brief(args.prompt, config))
    print(json.dumps(payload.__dict__, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
