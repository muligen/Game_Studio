from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class DesignAgent:
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

        profile = AgentProfileLoader().load("design")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root,
            profile=profile,
            session_id=session_id,
            resume_session=resume_session,
        )

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "design",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "design"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal}
        try:
            payload = self._claude_runner.generate("design", llm_context)
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"design_brief": self._fallback_patch(state)}
        else:
            state_patch["telemetry"] = {"design_brief": self._payload_to_design_brief(payload)}
            trace["fallback_used"] = False

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_patch(state: RuntimeState) -> dict[str, object]:
        prompt = state.goal.get("prompt")
        summary = prompt if isinstance(prompt, str) and prompt.strip() else "Draft a design brief"
        return {
            "title": "Design Brief Draft",
            "summary": summary,
            "core_rules": [],
            "acceptance_criteria": [],
            "open_questions": [],
        }

    @staticmethod
    def _payload_to_design_brief(payload: object) -> dict[str, object]:
        return {
            "title": payload.title,
            "summary": payload.summary,
            "core_rules": payload.core_rules,
            "acceptance_criteria": payload.acceptance_criteria,
            "open_questions": payload.open_questions,
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
