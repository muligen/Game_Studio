from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class QualityAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader().load("quality")
        self._claude_runner = ClaudeRoleAdapter(project_root=project_root, profile=profile)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "quality",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "quality"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal}
        try:
            payload = self._claude_runner.generate("quality", llm_context)
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"quality_report": self._fallback_patch()}
        else:
            state_patch["telemetry"] = {"quality_report": self._payload_to_quality_report(payload)}
            trace["fallback_used"] = False

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_patch() -> dict[str, object]:
        return {
            "summary": "Prepared a deterministic quality fallback report.",
            "ready": False,
            "risks": ["Claude quality report unavailable."],
            "follow_ups": [],
        }

    @staticmethod
    def _payload_to_quality_report(payload: object) -> dict[str, object]:
        return {
            "summary": payload.summary,
            "ready": payload.ready,
            "risks": payload.risks,
            "follow_ups": payload.follow_ups,
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
