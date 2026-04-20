from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ModeratorAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader(repo_root=project_root).load("moderator")
        self._claude_runner = ClaudeRoleAdapter(project_root=project_root, profile=profile)

    def prepare(self, state: RuntimeState) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_prepare", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_prepare"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "prepare"}
        try:
            payload = self._claude_runner.generate("moderator_prepare", context)
            state_patch["telemetry"] = {"moderator_prepare": self._prepare_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_prepare": self._fallback_prepare(state)}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    def summarize(self, state: RuntimeState, *, opinions: dict) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_summarize", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_summarize"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "summarize", "opinions": opinions}
        try:
            payload = self._claude_runner.generate("moderator_summary", context)
            state_patch["telemetry"] = {"moderator_summary": self._summary_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_summary": self._fallback_summary()}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    def minutes(self, state: RuntimeState, *, all_context: dict) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_minutes", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_minutes"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "minutes", **all_context}
        try:
            payload = self._claude_runner.generate("moderator_minutes", context)
            state_patch["telemetry"] = {"moderator_minutes": self._minutes_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_minutes": self._fallback_minutes(state)}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    @staticmethod
    def _prepare_payload(payload: object) -> dict[str, object]:
        return {
            "agenda": payload.agenda,
            "attendees": payload.attendees,
            "focus_questions": payload.focus_questions,
        }

    @staticmethod
    def _summary_payload(payload: object) -> dict[str, object]:
        return {
            "consensus_points": payload.consensus_points,
            "conflict_points": payload.conflict_points,
            "conflict_resolution_needed": payload.conflict_resolution_needed,
        }

    @staticmethod
    def _minutes_payload(payload: object) -> dict[str, object]:
        return {
            "title": payload.title,
            "summary": payload.summary,
            "decisions": payload.decisions,
            "action_items": payload.action_items,
            "pending_user_decisions": payload.pending_user_decisions,
        }

    @staticmethod
    def _fallback_prepare(state: RuntimeState) -> dict[str, object]:
        return {
            "agenda": [str(state.goal.get("prompt", ""))],
            "attendees": ["design", "dev", "qa"],
            "focus_questions": [],
        }

    @staticmethod
    def _fallback_summary() -> dict[str, object]:
        return {
            "consensus_points": [],
            "conflict_points": [],
            "conflict_resolution_needed": [],
        }

    @staticmethod
    def _fallback_minutes(state: RuntimeState) -> dict[str, object]:
        return {
            "title": "Meeting Notes",
            "summary": str(state.goal.get("prompt", "")),
            "decisions": [],
            "action_items": [],
            "pending_user_decisions": [],
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
