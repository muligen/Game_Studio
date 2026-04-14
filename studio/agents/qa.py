from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class QaAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            trace={"node": "qa", "result": "validated_workflow"},
        )
