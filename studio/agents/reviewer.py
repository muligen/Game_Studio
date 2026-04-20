from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ReviewerAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader(repo_root=project_root).load("reviewer")
        self._claude_runner = ClaudeRoleAdapter(project_root=project_root, profile=profile)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        raw = kwargs.get("artifact_payload", {})
        if not isinstance(raw, dict):
            artifact_payload: dict[str, object] = {}
        else:
            artifact_payload = raw
        trace: dict[str, object] = {
            "node": "reviewer",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {"plan": {"current_node": "reviewer"}}

        llm_context = {"artifact_payload": artifact_payload}
        try:
            payload = self._claude_runner.generate(
                "reviewer",
                llm_context,
            )
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            decision = self._fallback_decision(artifact_payload)
        else:
            decision = self._map_decision(payload.decision)
            state_patch["risks"] = payload.risks
            trace["fallback_used"] = False

        trace["decision"] = decision.value
        return NodeResult(
            decision=decision,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_decision(artifact_payload: dict[str, object]) -> NodeDecision:
        return NodeDecision.CONTINUE if "title" in artifact_payload else NodeDecision.RETRY

    @staticmethod
    def _map_decision(decision: str) -> NodeDecision:
        return NodeDecision.CONTINUE if decision == "continue" else NodeDecision.RETRY

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
