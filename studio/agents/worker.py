from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studio.llm import ClaudeWorkerAdapter, ClaudeWorkerError
from studio.schemas.artifact import ArtifactRecord
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class WorkerAgent:
    def __init__(
        self,
        claude_runner: ClaudeWorkerAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._claude_runner = claude_runner or ClaudeWorkerAdapter(project_root=project_root)

    def run(self, state: RuntimeState, **kwargs: object) -> NodeResult:
        prompt = state.goal["prompt"]
        if not isinstance(prompt, str):
            raise TypeError("goal.prompt must be a string")

        payload = self._fallback_payload(prompt)
        trace = {
            "node": "worker",
            "llm_provider": "claude",
            "fallback_used": True,
        }
        try:
            enabled = self._claude_runner.is_enabled()
        except ClaudeWorkerError as exc:
            trace["fallback_reason"] = str(exc)
            enabled = False

        if enabled:
            try:
                claude_payload = self._run_claude_in_thread(prompt)
            except ClaudeWorkerError as exc:
                trace["fallback_reason"] = str(exc)
            else:
                payload = {
                    "title": claude_payload.title,
                    "summary": claude_payload.summary,
                    "genre": claude_payload.genre,
                }
                trace["fallback_used"] = False
        else:
            trace.setdefault("fallback_reason", "claude_disabled")

        artifact = ArtifactRecord(
            artifact_id="concept-draft",
            artifact_type="design_brief",
            source_node="worker",
            payload=payload,
        )
        return NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={"plan": {"current_node": "worker"}},
            artifacts=[artifact],
            trace=trace,
        )

    @staticmethod
    def _fallback_payload(prompt: str) -> dict[str, str]:
        return {
            "title": "Moonwell Garden",
            "summary": prompt,
            "genre": "2d cozy strategy",
        }

    def _run_claude_in_thread(self, prompt: str):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._claude_runner.generate_design_brief, prompt)
            return future.result()

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
