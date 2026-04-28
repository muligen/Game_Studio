from __future__ import annotations

import os
import re
import subprocess
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


Runner = Callable[..., subprocess.CompletedProcess[str]]


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


def _default_hook_project(environ: Mapping[str, str]) -> Path:
    explicit = environ.get("CC_LANGFUSE_HOOK_PROJECT")
    if explicit:
        return Path(explicit)
    home = environ.get("HOME") or environ.get("USERPROFILE")
    if home:
        return Path(home) / ".claude" / "hooks" / "langfuse-claudecode"
    return Path.home() / ".claude" / "hooks" / "langfuse-claudecode"


def build_upstream_command(environ: Mapping[str, str]) -> list[str]:
    project = _default_hook_project(environ)
    script = project / "langfuse_hook.py"
    return ["uv", "run", "--project", str(project), "python", str(script)]


def _credentials_present(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("LANGFUSE_PUBLIC_KEY") and environ.get("LANGFUSE_SECRET_KEY"))


def run_hook(
    *,
    stdin_text: str,
    environ: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> HookResult:
    env = normalize_env(environ or os.environ)
    if not _is_truthy(env.get("TRACE_TO_LANGFUSE"), default=False):
        return HookResult(0, "Langfuse tracing disabled")
    if not _credentials_present(env):
        return HookResult(0, "Langfuse credentials missing")

    command = build_upstream_command(env)
    hard_fail = _is_truthy(env.get("CC_LANGFUSE_HARD_FAIL"), default=False)
    try:
        completed = runner(
            command,
            input=stdin_text,
            text=True,
            env=env,
            capture_output=True,
        )
    except Exception as exc:
        if hard_fail:
            return HookResult(1, f"Langfuse hook failed: {exc}")
        return HookResult(0, f"Langfuse hook failed open: {exc}")

    if completed.returncode != 0:
        stderr = getattr(completed, "stderr", "") or ""
        message = stderr.strip() or f"upstream hook exited {completed.returncode}"
        if hard_fail:
            return HookResult(completed.returncode, message)
        return HookResult(0, f"Langfuse hook failed open: {message}")

    return HookResult(0, "Langfuse hook delegated")


def main() -> int:
    stdin_text = sys.stdin.read()
    result = run_hook(stdin_text=stdin_text)
    if result.message:
        print(result.message, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
