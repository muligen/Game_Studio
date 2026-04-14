from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DevAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"node_name": "dev"},
            trace={"node": "dev", "result": "implemented_changes"},
        )
