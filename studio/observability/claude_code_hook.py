from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class HookResult:
    exit_code: int
    message: str


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSEY:
        return False
    return default


def agent_role_from_project_dir(project_dir: str | Path | None) -> str:
    if project_dir is None or not str(project_dir).strip():
        return "unknown"
    path = Path(project_dir)
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "agents" and index > 0 and parts[index - 1] == ".claude":
            return parts[index + 1]
    return path.name or "unknown"


def _safe_environment_name(role: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", role.strip().lower()).strip("-")
    if not normalized:
        normalized = "unknown"
    return f"game-studio-{normalized}"[:40]


def normalize_env(environ: Mapping[str, str]) -> dict[str, str]:
    env = dict(environ)
    base_url = env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST")
    if base_url:
        env["LANGFUSE_BASE_URL"] = base_url
        env["LANGFUSE_HOST"] = base_url
    role = agent_role_from_project_dir(env.get("CLAUDE_PROJECT_DIR"))
    env.setdefault("CC_LANGFUSE_AGENT_ROLE", role)
    env.setdefault("CC_LANGFUSE_ENVIRONMENT", _safe_environment_name(role))
    return env


def _credentials_present(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("LANGFUSE_PUBLIC_KEY") and environ.get("LANGFUSE_SECRET_KEY"))


def run_hook(
    *,
    stdin_text: str,
    environ: Mapping[str, str] | None = None,
) -> HookResult:
    env = normalize_env(environ or os.environ)

    if not _is_truthy(env.get("TRACE_TO_LANGFUSE"), default=False):
        return HookResult(0, "Langfuse tracing disabled")
    if not _credentials_present(env):
        return HookResult(0, "Langfuse credentials missing")

    try:
        from studio.observability.langfuse_tracer import process_transcript
        message = process_transcript(stdin_text, environ=env)
        return HookResult(0, message)
    except Exception as exc:
        hard_fail = _is_truthy(env.get("CC_LANGFUSE_HARD_FAIL"), default=False)
        if hard_fail:
            return HookResult(1, f"Langfuse hook failed: {exc}")
        return HookResult(0, f"Langfuse hook failed open: {exc}")


def main() -> int:
    stdin_text = sys.stdin.read()
    result = run_hook(stdin_text=stdin_text)
    if result.message:
        print(result.message, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
