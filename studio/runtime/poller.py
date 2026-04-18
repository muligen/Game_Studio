from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import as_completed
from pathlib import Path

from studio.runtime import pool
from studio.runtime.executor import DeliveryWorkflowExecutor, DesignWorkflowExecutor
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


async def _broadcast_changes(changes: list[dict[str, str]]) -> None:
    """Broadcast entity changes via WebSocket."""
    from studio.api.websocket import broadcast_entity_changed

    for change in changes:
        await broadcast_entity_changed(**change)


class WorkflowPoller:
    """Background poller that auto-discovers eligible requirements and runs workflows."""

    def __init__(
        self,
        workspace_path: Path,
        interval: int | None = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.interval = interval or int(os.environ.get("GAME_STUDIO_POLL_INTERVAL", "10"))
        self._running = False

    async def start(self) -> None:
        """Start the polling loop. Runs until stop() is called."""
        self._running = True
        logger.info("WorkflowPoller started (interval=%ds, workspace=%s)", self.interval, self.workspace_path)
        while self._running:
            try:
                changed = await asyncio.get_event_loop().run_in_executor(None, self._tick)
                # Broadcast changes via WebSocket
                if changed:
                    await _broadcast_changes(changed)
            except Exception:
                logger.exception("poller tick failed")
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("WorkflowPoller stopping")

    def _tick(self) -> list[dict[str, str]]:
        """Single scan: find eligible requirements and execute in parallel."""
        workspace = StudioWorkspace(self.workspace_path)
        workspace.ensure_layout()

        design_eligible = []
        delivery_eligible = []
        for req in workspace.requirements.list_all():
            if req.status in ("draft", "designing"):
                design_eligible.append(req)
            elif req.status == "approved":
                delivery_eligible.append(req)

        if not design_eligible and not delivery_eligible:
            return []

        workspace_name = (
            str(self.workspace_path.parent)
            if self.workspace_path.name == ".studio-data"
            else str(self.workspace_path)
        )

        design_executor = DesignWorkflowExecutor()
        delivery_executor = DeliveryWorkflowExecutor()

        # Submit all eligible requirements to the shared agent pool so pool
        # status telemetry can reflect both design and delivery work.
        future_to_req: dict[object, tuple[object, str]] = {}
        for req in design_eligible:
            logger.info("poller picked up requirement %s for design (status=%s)", req.id, req.status)
            future = pool.submit_agent(
                "design",
                req.id,
                req.title,
                design_executor.run,
                workspace,
                req,
                workspace_root=str(self.workspace_path),
            )
            future_to_req[future] = (req, "design")

        for req in delivery_eligible:
            logger.info("poller picked up requirement %s for delivery (status=%s)", req.id, req.status)
            future = pool.submit_agent(
                "delivery",
                req.id,
                req.title,
                delivery_executor.run,
                workspace,
                req,
                workspace_root=str(self.workspace_path),
            )
            future_to_req[future] = (req, "delivery")

        # Collect results as they complete
        changed: list[dict[str, str]] = []
        for future in as_completed(future_to_req):
            req, workflow = future_to_req[future]
            try:
                result = future.result()
                changed.append({
                    "workspace": workspace_name,
                    "entity_type": "requirement",
                    "entity_id": req.id,
                    "action": "updated",
                })
                if workflow == "design":
                    design_doc_id = result.get("design_doc_id")
                    if design_doc_id:
                        changed.append({
                            "workspace": workspace_name,
                            "entity_type": "design_doc",
                            "entity_id": str(design_doc_id),
                            "action": "created",
                        })
            except Exception:
                logger.exception("executor failed for requirement %s (%s workflow)", req.id, workflow)
                # Roll back so the poller can retry on the next tick
                rollback_status = "draft" if workflow == "design" else "approved"
                try:
                    rolled_back = req.model_copy(update={"status": rollback_status})
                    workspace.requirements.save(rolled_back)
                    logger.info("rolled back requirement %s to %s", req.id, rollback_status)
                except Exception:
                    logger.exception("failed to roll back requirement %s", req.id)

        return changed
