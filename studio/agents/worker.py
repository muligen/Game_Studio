from __future__ import annotations

from studio.schemas.artifact import ArtifactRecord
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class WorkerAgent:
    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        prompt = state.goal["prompt"]
        if not isinstance(prompt, str):
            raise TypeError("goal.prompt must be a string")
        artifact = ArtifactRecord(
            artifact_id="concept-draft",
            artifact_type="design_brief",
            source_node="worker",
            payload={
                "title": "Moonwell Garden",
                "summary": prompt,
                "genre": "2d cozy strategy",
            },
        )
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"plan": {"current_node": "worker"}},
            artifacts=[artifact],
            trace={"node": "worker"},
        )
