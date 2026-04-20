from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class AgentProfileError(RuntimeError):
    pass


class AgentProfileNotFoundError(AgentProfileError):
    pass


class AgentProfileValidationError(AgentProfileError):
    pass


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    system_prompt: str
    claude_project_root: Path
