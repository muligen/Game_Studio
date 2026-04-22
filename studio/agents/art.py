from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ArtAgent:
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

        profile = AgentProfileLoader(repo_root=project_root).load("art")
        self._claude_runner = ClaudeRoleAdapter(
            project_root=project_root,
            profile=profile,
            session_id=session_id,
            resume_session=resume_session,
        )

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        trace: dict[str, object] = {
            "node": "art",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        state_patch: dict[str, object] = {
            "plan": {"current_node": "art"},
            "telemetry": {},
        }

        llm_context = {"goal": state.goal}
        try:
            payload = self._claude_runner.generate("art", llm_context)
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"art_report": self._fallback_patch()}
        else:
            state_patch["telemetry"] = {"art_report": self._payload_to_art_report(payload)}
            trace["fallback_used"] = False

        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch=state_patch,
            trace=trace,
        )

    @staticmethod
    def _fallback_patch() -> dict[str, object]:
        return {
            "summary": "Prepared a deterministic art fallback report.",
            "style_direction": "clean placeholder concept art",
            "asset_list": [],
        }

    @staticmethod
    def _payload_to_art_report(payload: object) -> dict[str, object]:
        return {
            "summary": payload.summary,
            "style_direction": payload.style_direction,
            "asset_list": payload.asset_list,
        }

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
