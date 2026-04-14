from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ArtAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"node_name": "art"},
            trace={"node": "art", "result": "sketched_visual_direction"},
        )
