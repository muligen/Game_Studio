from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DeliveryPlannerAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
        session_id: str | None = None,
        resume_session: bool = False,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader().load("delivery_planner")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root,
            profile=profile,
            session_id=session_id,
            resume_session=resume_session,
        )

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "delivery_planner",
            "llm_provider": "claude",
            "fallback_used": False,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "delivery_planner"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal, "phase": "plan_generation"}
        payload = self._claude_runner.generate("delivery_planner", llm_context)
        state_patch["telemetry"] = {"delivery_plan": self._payload_to_dict(payload)}

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    def generate_payload(self, context: dict[str, object]) -> dict[str, object]:
        payload = self._claude_runner.generate("delivery_planner", context)
        return self._payload_to_dict(payload)

    @staticmethod
    def _payload_to_dict(payload: object) -> dict[str, object]:
        return {
            "tasks": [
                {
                    "title": t.title,
                    "description": t.description,
                    "owner_agent": t.owner_agent,
                    "depends_on": t.depends_on,
                    "acceptance_criteria": t.acceptance_criteria,
                    "source_evidence": t.source_evidence,
                }
                for t in payload.tasks
            ],
            "decision_gate": {
                "items": [
                    {
                        "question": gi.question,
                        "context": gi.context,
                        "options": gi.options,
                        "source_evidence": gi.source_evidence,
                    }
                    for gi in payload.decision_gate.items
                ],
            },
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
