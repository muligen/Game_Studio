from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from studio.storage.git_tracker import GitTracker


_HOOK_PATH_PATTERN = re.compile(r'(?P<quote>["\'])(?P<path>\.\.?[/\\][^"\']+?)(?P=quote)')


class AgentProfileLike(Protocol):
    system_prompt: str
    claude_project_root: Path


def resolve_agent_project_dir(
    *,
    project_root: Path,
    workspace_root: Path | None,
    context: dict[str, object] | None,
) -> Path:
    """Resolve the target project directory for a Claude agent invocation."""
    _ = workspace_root
    context = context or {}
    goal = context.get("goal")
    goal_dict = goal if isinstance(goal, dict) else {}

    explicit = goal_dict.get("project_dir")
    if isinstance(explicit, str) and explicit.strip():
        path = Path(explicit)
        if not path.is_absolute():
            path = project_root / path
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    project_id = _first_non_empty_str(
        goal_dict.get("project_id"),
        context.get("project_id"),
        getattr(context, "project_id", None),
    )
    if project_id is None:
        raise ValueError("missing project context for Claude agent invocation")

    return GitTracker(repo_root=project_root, project_id=project_id).ensure_project_dir().resolve()


def load_agent_settings(profile: AgentProfileLike, project_dir: Path) -> str | None:
    """Load agent-local Claude settings as JSON for an invocation rooted at project_dir."""
    _ = project_dir
    agent_config_dir = profile.claude_project_root.resolve()
    settings_path = agent_config_dir / ".claude" / "settings.local.json"
    if not settings_path.is_file():
        return None
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    rewritten = _rewrite_relative_hook_commands(payload, agent_config_dir)
    return json.dumps(rewritten, ensure_ascii=False)


def agent_prompt_context(profile: AgentProfileLike, project_dir: Path) -> str:
    """Return project-scope guardrails plus agent-local CLAUDE.md content."""
    agent_config_dir = profile.claude_project_root.resolve()
    parts = [
        "Project-scoped execution:",
        f"- Current working directory is the target project: {project_dir.resolve()}",
        f"- Agent configuration directory: {agent_config_dir}",
        "- Do not inspect or modify the Game Studio repository unless the task explicitly asks to maintain Game Studio itself.",
        "- Treat all relative file paths as relative to the target project directory.",
    ]
    claude_md = agent_config_dir / "CLAUDE.md"
    if claude_md.is_file():
        try:
            content = claude_md.read_text(encoding="utf-8").strip()
        except OSError:
            content = ""
        if content:
            parts.extend(["", "Agent-local CLAUDE.md:", content])
    return "\n".join(parts)


def _first_non_empty_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rewrite_relative_hook_commands(value: Any, agent_config_dir: Path) -> Any:
    if isinstance(value, dict):
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            if key == "command" and isinstance(item, str):
                rewritten[key] = _rewrite_command_paths(item, agent_config_dir)
            else:
                rewritten[key] = _rewrite_relative_hook_commands(item, agent_config_dir)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_relative_hook_commands(item, agent_config_dir) for item in value]
    return value


def _rewrite_command_paths(command: str, agent_config_dir: Path) -> str:
    def _replace(match: re.Match[str]) -> str:
        raw_path = match.group("path")
        path = Path(raw_path)
        if path.is_absolute():
            return match.group(0)
        resolved = (agent_config_dir / path).resolve()
        return f'{match.group("quote")}{resolved}{match.group("quote")}'

    return _HOOK_PATH_PATTERN.sub(_replace, command)
