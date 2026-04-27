"""Background poller that picks up and executes ready delivery tasks.

Each delivery task has an owner_agent (design/dev/qa/art/reviewer/quality).
This poller discovers tasks with status="ready", starts them (acquires lease),
runs the appropriate agent, and completes them with results.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from studio.runtime import pool
from studio.storage.delivery_plan_service import DeliveryPlanService
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
        """Single scan: find ready tasks and execute them."""
        service = DeliveryPlanService(self.workspace_path)
        board = service.list_board()

        ready_tasks = [t for t in board["tasks"] if t.status == "ready"]
        if not ready_tasks:
            return

        logger.info("Found %d ready delivery tasks", len(ready_tasks))

        for task in ready_tasks:
            self._execute_task(service, task)

    def _execute_task(
        self,
        service: DeliveryPlanService,
        task: Any,
    ) -> None:
        """Execute a single delivery task."""
        logger.info(
            "Executing task %s (owner=%s, title=%s)",
            task.id,
            task.owner_agent,
            task.title,
        )

        future = pool.submit_agent(
            task.owner_agent,
            task.requirement_id,
            task.title,
            self._run_task_agent,
            service,
            task,
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
    ) -> dict[str, object]:
        """Run the agent for a single delivery task."""
        try:
            started_task = service.start_task(task.id)
        except ValueError as exc:
            logger.warning("Cannot start task %s: %s", task.id, exc)
            return {"error": str(exc)}

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
            },
        )

        try:
            result = agent.run(state)
            logger.info("Agent %s completed for task %s", agent_name, task.id)
        except Exception:
            logger.exception("Agent %s failed for task %s", agent_name, task.id)
            result = None

        summary = f"{agent_name} completed: {task.title}"
        if result and result.trace and result.trace.get("fallback_used"):
            summary += " (fallback)"

        complete_result = service.complete_task(
            task_id=task.id,
            summary=summary,
            output_artifact_ids=[],
            changed_files=[],
            tests_or_checks=[],
            follow_up_notes=[],
        )

        return {
            "task_id": task.id,
            "summary": summary,
            "execution_result": complete_result["execution_result"].model_dump(),
        }
