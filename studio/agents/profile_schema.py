from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints


def _reject_empty_claude_project_root(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        raise ValueError("claude_project_root must be a non-empty string")
    return value


class AgentProfileError(RuntimeError):
    pass


class AgentProfileNotFoundError(AgentProfileError):
    pass


class AgentProfileValidationError(AgentProfileError):
    pass


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1),
    ]
    system_prompt: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1),
    ]
    claude_project_root: Annotated[Path, BeforeValidator(_reject_empty_claude_project_root)]
