from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class QaAgent:
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

        profile = AgentProfileLoader(repo_root=project_root).load("qa")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root,
            profile=profile,
            session_id=session_id,
            resume_session=resume_session,
        )

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "qa",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "qa"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal}
        try:
            payload = self._claude_runner.generate("qa", llm_context)
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"qa_report": self._fallback_patch()}
        else:
            state_patch["telemetry"] = {"qa_report": self._payload_to_qa_report(payload)}
            trace["fallback_used"] = False

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_patch() -> dict[str, object]:
        return {
            "summary": "Prepared a deterministic QA fallback report.",
            "passed": False,
            "suggested_bug": "QA fallback used because Claude output was unavailable.",
        }

    @staticmethod
    def _payload_to_qa_report(payload: object) -> dict[str, object]:
        return {
            "summary": payload.summary,
            "passed": payload.passed,
            "suggested_bug": payload.suggested_bug,
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
