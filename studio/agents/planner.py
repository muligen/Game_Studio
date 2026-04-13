from __future__ import annotations

from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class PlannerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "plan": {
                    "graph_name": "game_studio_demo",
                    "current_node": "planner",
                    "pending_nodes": ["worker", "reviewer"],
                    "completed_nodes": [],
                }
            },
            trace={"node": "planner", "reason": "initialized demo graph"},
        )
