from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from studio.agents.profile_schema import AgentProfile, AgentProfileNotFoundError, AgentProfileValidationError


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _profile_path(agent_name: str) -> Path:
    return _repo_root() / "studio" / "agents" / "profiles" / f"{agent_name}.yaml"


def load_agent_profile(agent_name: str) -> AgentProfile:
    path = _profile_path(agent_name)
    if not path.exists():
        raise AgentProfileNotFoundError(f"agent profile not found: {agent_name}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive, covered by validation path
        raise AgentProfileValidationError(f"invalid yaml for agent profile: {agent_name}") from exc

    if not isinstance(raw, Mapping):
        raise AgentProfileValidationError(f"agent profile must be a mapping: {agent_name}")

    data: dict[str, Any] = dict(raw)
    required_fields = {"name", "system_prompt", "claude_project_root"}
    missing_fields = sorted(required_fields - data.keys())
    if missing_fields:
        raise AgentProfileValidationError(
            f"missing required agent profile fields: {', '.join(missing_fields)}"
        )

    if data["name"] != agent_name:
        raise AgentProfileValidationError(
            f"agent profile name mismatch: expected {agent_name}, found {data['name']}"
        )

    repo_root = _repo_root()
    claude_project_root = Path(data["claude_project_root"])
    if not claude_project_root.is_absolute():
        claude_project_root = (repo_root / claude_project_root).resolve()
    else:
        claude_project_root = claude_project_root.resolve()

    if not claude_project_root.exists() or not claude_project_root.is_dir():
        raise AgentProfileValidationError(
            f"missing or invalid claude project root: {claude_project_root}"
        )

    data["claude_project_root"] = claude_project_root

    try:
        return AgentProfile.model_validate(data)
    except ValidationError as exc:
        raise AgentProfileValidationError("invalid agent profile") from exc
