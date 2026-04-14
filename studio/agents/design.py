from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DesignAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"node_name": "design"},
            trace={"node": "design", "result": "drafted_design"},
        )
