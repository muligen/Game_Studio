from __future__ import annotations

from pathlib import Path

from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DevAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._claude_runner = claude_runner or ClaudeRoleAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "dev",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "dev"},
            "telemetry": {},
        }

        try:
            payload = self._claude_runner.generate("dev", {"goal": state.goal})
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"dev_report": self._fallback_patch()}
        else:
            state_patch["telemetry"] = {"dev_report": self._payload_to_dev_report(payload)}
            trace["fallback_used"] = False

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_patch() -> dict[str, object]:
        return {
            "summary": "Prepared a deterministic dev fallback report.",
            "changes": [],
            "checks": [],
            "follow_ups": [],
        }

    @staticmethod
    def _payload_to_dev_report(payload: object) -> dict[str, object]:
        return {
            "summary": payload.summary,
            "changes": payload.changes,
            "checks": payload.checks,
            "follow_ups": payload.follow_ups,
        }
