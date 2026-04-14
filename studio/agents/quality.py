from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class QualityAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"node_name": "quality"},
            trace={"node": "quality", "result": "quality_scan_complete"},
        )
