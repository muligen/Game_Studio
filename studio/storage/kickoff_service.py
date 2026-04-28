"""Background kickoff meeting service.

Runs the meeting graph asynchronously and tracks progress via KickoffTask records.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from studio.api.websocket import broadcast_entity_changed
from studio.llm import ClaudeRoleError
from studio.runtime.graph import build_meeting_graph
from studio.schemas.clarification import RequirementClarificationSession
from studio.schemas.kickoff_task import KickoffTask
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.session_registry import SessionRegistry
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)

_MANAGED_AGENTS = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
_DELIVERY_PLANNING_ATTEMPTS = 2


class KickoffService:
    def __init__(self, workspace_root: Path, project_root: Path | None = None) -> None:
        self._ws = StudioWorkspace(workspace_root)
        self._ws.ensure_layout()
        self._workspace_root = workspace_root
        self._project_root = project_root or (
            workspace_root.parent if workspace_root.name == ".studio-data" else None
        )
        self._running_tasks: dict[str, asyncio.Task] = {}

    def start_kickoff(
        self,
        *,
        workspace: str,
        session_id: str,
        requirement_id: str,
        meeting_context: dict,
    ) -> KickoffTask:
        task_id = f"kickoff_{uuid.uuid4().hex[:8]}"
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC).isoformat()
        task = KickoffTask(
            id=task_id,
            session_id=session_id,
            requirement_id=requirement_id,
            workspace=workspace,
            project_id=project_id,
            status="pending",
        )
        self._ws.kickoff_tasks.save(task)

        registry = SessionRegistry(self._workspace_root)
        registry.create_all(project_id, requirement_id, _MANAGED_AGENTS)

        coro = self._run_meeting_graph(
            task_id=task_id,
            workspace=workspace,
            requirement_id=requirement_id,
            project_id=project_id,
            meeting_context=meeting_context,
        )
        async_task = asyncio.create_task(coro)
        self._running_tasks[task_id] = async_task
        async_task.add_done_callback(lambda _t: self._running_tasks.pop(task_id, None))

        return task

    def get_task(self, task_id: str) -> KickoffTask:
        return self._ws.kickoff_tasks.get(task_id)

    async def _run_meeting_graph(
        self,
        *,
        task_id: str,
        workspace: str,
        requirement_id: str,
        project_id: str,
        meeting_context: dict,
    ) -> None:
        self._update_task(task_id, status="running")

        try:
            graph = build_meeting_graph()
            result = await graph.ainvoke(
                {
                    "workspace_root": str(self._workspace_root),
                    "project_root": str(self._project_root) if self._project_root else "",
                    "requirement_id": requirement_id,
                    "user_intent": f"Kickoff: {meeting_context.get('summary', '')}",
                    "project_id": project_id,
                    "meeting_context": meeting_context,
                }
            )

            minutes = result.get("minutes", {})
            meeting_id = minutes.get("id", "")

            meeting_result = {
                "project_id": project_id,
                "requirement_id": requirement_id,
                "meeting_id": meeting_id,
                "status": "kickoff_complete",
                "meeting": {
                    "id": meeting_id,
                    "title": str(minutes.get("title", "")),
                    "summary": str(minutes.get("summary", "")),
                    "attendees": [str(a) for a in minutes.get("attendees", [])],
                    "consensus_points": [str(c) for c in minutes.get("consensus", [])],
                    "conflict_points": [str(c) for c in minutes.get("conflicts", [])],
                    "pending_user_decisions": [
                        str(d) for d in minutes.get("pending_user_decisions", [])
                    ],
                },
            }

            if meeting_id:
                await asyncio.to_thread(
                    self._generate_delivery_plan_with_retry,
                    meeting_id,
                    project_id,
                )

            self._update_task(
                task_id,
                status="completed",
                meeting_result=meeting_result,
            )

            # Transition requirement to approved
            try:
                from studio.domain.requirement_flow import transition_requirement
                req = self._ws.requirements.get(requirement_id)
                if req.status in ("designing", "pending_user_review", "draft"):
                    req = transition_requirement(req, "approved")
                    self._ws.requirements.save(req)
            except Exception:
                logger.exception("Failed to auto-advance requirement %s to approved", requirement_id)

            # Update clarification session to completed
            try:
                kickoff_task = self._ws.kickoff_tasks.get(task_id)
                session = self._ws.clarifications.get(kickoff_task.session_id)
                session = session.model_copy(update={
                    "status": "completed",
                    "project_id": project_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
                self._ws.clarifications.save(session)
            except (FileNotFoundError, ValueError):
                logger.warning("Could not update session status for task %s", task_id)

            await broadcast_entity_changed(
                workspace=workspace,
                entity_type="kickoff_task",
                entity_id=task_id,
                action="completed",
            )

        except Exception as exc:
            logger.exception("Kickoff task %s failed", task_id)
            failed_update: dict[str, object] = {"status": "failed", "error": str(exc)}
            if "meeting_result" in locals():
                failed_update["meeting_result"] = meeting_result
            self._update_task(task_id, **failed_update)
            await broadcast_entity_changed(
                workspace=workspace,
                entity_type="kickoff_task",
                entity_id=task_id,
                action="failed",
            )

    def _update_task(self, task_id: str, **kwargs) -> None:
        task = self._ws.kickoff_tasks.get(task_id)
        updated = task.model_copy(update=kwargs)
        self._ws.kickoff_tasks.save(updated)

    def _generate_delivery_plan_with_retry(self, meeting_id: str, project_id: str) -> None:
        delivery_service = DeliveryPlanService(
            self._workspace_root,
            project_root=self._project_root,
        )
        last_delivery_error: Exception | None = None
        for _ in range(_DELIVERY_PLANNING_ATTEMPTS):
            try:
                delivery_service.generate_plan(
                    meeting_id=meeting_id,
                    project_id=project_id,
                )
                return
            except (ValueError, FileNotFoundError, ClaudeRoleError) as exc:
                last_delivery_error = exc

        if last_delivery_error is not None:
            raise last_delivery_error
