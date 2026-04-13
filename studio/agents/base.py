from __future__ import annotations

from typing import Protocol

from studio.schemas.runtime import NodeResult, RuntimeState


class RuntimeAgent(Protocol):
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        ...
