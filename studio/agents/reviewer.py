from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ReviewerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        raw = kwargs.get("artifact_payload", {})
        if not isinstance(raw, dict):
            artifact_payload: dict[str, object] = {}
        else:
            artifact_payload = raw
        decision = NodeDecision.CONTINUE if "title" in artifact_payload else NodeDecision.RETRY
        return NodeResult(
            decision=decision,
            state_patch={"plan": {"current_node": "reviewer"}},
            trace={"node": "reviewer", "decision": decision.value},
        )
