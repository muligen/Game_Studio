from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class QualityAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            trace={"node": "quality", "result": "quality_scan_complete"},
        )
