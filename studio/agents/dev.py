from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DevAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            trace={"node": "dev", "result": "implemented_changes"},
        )
