from __future__ import annotations

from typing import Annotated
from pathlib import Path

from pydantic import BaseModel, ConfigDict, StringConstraints


class AgentProfileError(RuntimeError):
    pass


class AgentProfileNotFoundError(AgentProfileError):
    pass


class AgentProfileValidationError(AgentProfileError):
    pass


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    system_prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    claude_project_root: Path
