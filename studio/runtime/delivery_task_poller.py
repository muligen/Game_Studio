"""Background poller that picks up and executes ready delivery tasks.

Each delivery task has an owner_agent (design/dev/qa/art/reviewer/quality).
This poller discovers tasks with status="ready", starts them (acquires lease),
runs the appropriate agent, and completes them with results.
"""
from __future__ import annotations

import asyncio
import logging
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from studio.runtime import pool
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.git_tracker import GitDiffResult, GitTracker
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


class DeliveryTaskPoller:
    """Background poller that picks up ready delivery tasks and executes them."""

    def __init__(
        self,
        workspace_path: Path,
        interval: int | None = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.interval = interval or int(os.environ.get("GAME_STUDIO_DELIVERY_POLL_INTERVAL", "5"))
        self._running = False

    async def start(self) -> None:
        """Start the polling loop. Runs until stop() is called."""
        self._running = True
        logger.info(
            "DeliveryTaskPoller started (interval=%ds, workspace=%s)",
            self.interval,
            self.workspace_path,
        )
        while self._running:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._tick)
            except Exception:
                logger.exception("delivery task poller tick failed")
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("DeliveryTaskPoller stopping")

    def _tick(self) -> None:
        """Single scan: recover stuck tasks, then find ready tasks and execute them."""
        self._recover_stuck_tasks()

        service = DeliveryPlanService(self.workspace_path)
        board = service.list_board()

        ready_tasks = [t for t in board["tasks"] if t.status == "ready"]
        if not ready_tasks:
            return

        logger.info("Found %d ready delivery tasks", len(ready_tasks))

        for task in ready_tasks:
            self._try_execute_task(service, task)

    def _recover_stuck_tasks(self) -> None:
        """Recover tasks that are stuck in in_progress with expired leases."""
        service = DeliveryPlanService(self.workspace_path)
        board = service.list_board()

        from datetime import datetime, UTC

        now = datetime.now(UTC)
        for task in board["tasks"]:
            if task.status == "in_progress":
                lease = service._lease_mgr.find(task.project_id, task.owner_agent)
                if lease and lease.status == "held":
                    try:
                        expires = datetime.fromisoformat(lease.expires_at)
                        if now > expires:
                            logger.warning(
                                "Recovering stuck task %s (lease expired at %s)",
                                task.id,
                                lease.expires_at,
                            )
                            pool.record_task_error(
                                task_id=task.id,
                                agent_type=task.owner_agent,
                                requirement_id=task.requirement_id,
                                error_type="stuck",
                                error_message=f"Task {task.id} lease expired",
                                details={
                                    "lease_expires_at": lease.expires_at,
                                    "task_title": getattr(task, "title", ""),
                                },
                            )
                            self._rollback_task(service, task)
                    except (ValueError, TypeError):
                        pass

    def _rollback_task(self, service: DeliveryPlanService, task: Any) -> None:
        """Roll back a stuck task to ready status and release its lease."""
        from studio.schemas.delivery import DeliveryTask

        try:
            service._lease_mgr.release(task.project_id, task.owner_agent)
        except Exception:
            logger.debug("No lease to release for %s/%s", task.project_id, task.owner_agent)

        rolled_back = DeliveryTask(
            id=task.id,
            plan_id=task.plan_id,
            meeting_id=task.meeting_id,
            requirement_id=task.requirement_id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            owner_agent=task.owner_agent,
            status="ready",
            depends_on_task_ids=list(task.depends_on_task_ids),
            acceptance_criteria=list(task.acceptance_criteria),
            meeting_snapshot=task.meeting_snapshot,
            decision_resolution_version=task.decision_resolution_version,
            created_at=task.created_at,
            updated_at=datetime.now(UTC).isoformat(),
        )
        service._ws.delivery_tasks.save(rolled_back)
        logger.info("Rolled back task %s to ready status", task.id)

    def _try_execute_task(
        self,
        service: DeliveryPlanService,
        task: Any,
    ) -> None:
        """Acquire lease and submit task to the agent pool.

        The lease is acquired BEFORE pool submission so that the task status
        changes to ``in_progress`` immediately.  This prevents the next tick
        from re-submitting the same task.
        """
        started_task = None
        try:
            started_task = service.start_task(task.id)
        except ValueError as exc:
            logger.warning("Cannot start task %s: %s", task.id, exc)
            return

        logger.info(
            "Executing task %s (owner=%s, title=%s)",
            task.id,
            started_task.owner_agent,
            task.title,
        )

        future = pool.submit_agent(
            started_task.owner_agent,
            started_task.requirement_id,
            task.title,
            self._run_task_agent,
            service,
            task,
            started_task,
        )

        def _on_done(_: object) -> None:
            try:
                result = future.result()
                logger.info("Task %s completed: %s", task.id, result)
            except Exception:
                logger.exception("Task %s failed", task.id)

        future.add_done_callback(_on_done)

    def _run_task_agent(
        self,
        service: DeliveryPlanService,
        task: Any,
        started_task: Any,
    ) -> dict[str, object]:
        """Run the agent for a single delivery task.

        ``started_task`` is the task with status=in_progress, already acquired
        by ``_try_execute_task()`` before pool submission.
        """
        try:
            return self._run_task_agent_inner(service, task, started_task)
        except Exception as exc:
            logger.exception("Unhandled error in _run_task_agent for task %s", task.id)
            pool.record_task_error(
                task_id=task.id,
                agent_type=task.owner_agent,
                requirement_id=task.requirement_id,
                error_type="failed",
                error_message=f"Unhandled error: {exc}",
                details={
                    "exception_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-2000:],
                    "task_title": getattr(task, "title", ""),
                    "task_description": getattr(task, "description", "")[:500],
                },
            )
            self._rollback_task(service, task)
            return {"error": f"Unhandled error for task {task.id}"}

    def _run_task_agent_inner(
        self,
        service: DeliveryPlanService,
        task: Any,
        started_task: Any,
    ) -> dict[str, object]:
        # Initialize git tracker and project directory
        repo_root = Path(service._ws.root).resolve()
        if repo_root.name == ".studio-data":
            repo_root = repo_root.parent
        tracker = GitTracker(repo_root=repo_root, project_id=started_task.project_id)
        tracker.ensure_project_dir()

        pre_state: dict[str, str] = {}
        try:
            pre_state = tracker.capture_state()
        except Exception:
            logger.warning("Failed to capture pre-execution state for %s", task.id)

        from studio.runtime.dispatcher import RuntimeDispatcher

        dispatcher = RuntimeDispatcher()

        agent_name = started_task.owner_agent
        agent = dispatcher.get(agent_name)

        from studio.schemas.runtime import RuntimeState

        state = RuntimeState(
            project_id=started_task.project_id,
            run_id=f"task_{started_task.id}",
            task_id=started_task.id,
            goal={
                "prompt": f"{task.title}\n\n{task.description}",
                "task_title": task.title,
                "task_description": task.description,
                "acceptance_criteria": task.acceptance_criteria,
                "project_dir": str(tracker.project_dir),
            },
        )

        result = None
        try:
            result = agent.run(state)
            logger.info("Agent %s completed for task %s", agent_name, task.id)
        except Exception as exc:
            logger.exception("Agent %s failed for task %s", agent_name, task.id)
            prompt_text = state.goal.get("prompt", "") if state.goal else ""
            pool.record_task_error(
                task_id=task.id,
                agent_type=agent_name,
                requirement_id=task.requirement_id,
                error_type="failed",
                error_message=f"Agent {agent_name}: {exc}",
                details={
                    "exception_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-2000:],
                    "task_title": task.title,
                    "task_description": task.description[:500],
                    "prompt": prompt_text[:2000],
                    "acceptance_criteria": task.acceptance_criteria,
                },
            )
            self._rollback_task(service, task)
            return {"error": f"Agent {agent_name} failed"}

        # Detect file changes
        diff = GitDiffResult(changed_files=[])
        commit_hash = ""
        try:
            diff = tracker.detect_changes(pre_state)
            if diff.has_changes:
                commit_hash = tracker.add_and_commit(
                    f"Task {task.id}: {task.title}\n\nAgent: {agent_name}"
                )
                logger.info(
                    "Task %s: %d files changed (commit=%s)",
                    task.id,
                    len(diff.changed_files),
                    commit_hash,
                )
        except Exception:
            logger.warning("Failed to detect/commit changes for task %s", task.id)

        summary = f"{agent_name} completed: {task.title}"
        if result and result.trace and result.trace.get("fallback_used"):
            summary += " (fallback)"

        changed_files = [c.path for c in diff.changed_files]

        try:
            complete_result = service.complete_task(
                task_id=task.id,
                summary=summary,
                output_artifact_ids=changed_files,
                changed_files=changed_files,
                tests_or_checks=[],
                follow_up_notes=[],
            )
        except Exception as exc:
            logger.exception("Failed to complete task %s, rolling back", task.id)
            pool.record_task_error(
                task_id=task.id,
                agent_type=agent_name,
                requirement_id=task.requirement_id,
                error_type="failed",
                error_message=f"Complete task failed: {exc}",
                details={
                    "exception_type": type(exc).__name__,
                    "traceback": traceback.format_exc()[-2000:],
                    "task_title": task.title,
                },
            )
            self._rollback_task(service, task)
            return {"error": "Failed to complete task"}

        return {
            "task_id": task.id,
            "summary": summary,
            "git_commit": commit_hash,
            "execution_result": complete_result["execution_result"].model_dump(),
        }
