from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from studio.runtime.executor import DesignWorkflowExecutor
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


class WorkflowPoller:
    """Background poller that auto-discovers eligible requirements and runs the design workflow."""

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
                await asyncio.get_event_loop().run_in_executor(None, self._tick)
            except Exception:
                logger.exception("poller tick failed")
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        logger.info("WorkflowPoller stopping")

    def _tick(self) -> None:
        """Single scan: find eligible requirements and execute."""
        workspace = StudioWorkspace(self.workspace_path)
        workspace.ensure_layout()

        requirements = workspace.requirements.list_all()
        executor = DesignWorkflowExecutor()

        for req in requirements:
            if self._is_eligible(req, workspace):
                logger.info("poller picked up requirement %s (status=%s)", req.id, req.status)
                try:
                    executor.run(
                        workspace,
                        req,
                        workspace_root=str(self.workspace_path),
                    )
                except Exception:
                    logger.exception("executor failed for requirement %s", req.id)
                    # Roll back to draft so the poller can retry on the next tick
                    if req.status in ("draft", "designing"):
                        try:
                            rolled_back = req.model_copy(update={"status": "draft"})
                            workspace.requirements.save(rolled_back)
                            logger.info("rolled back requirement %s to draft", req.id)
                        except Exception:
                            logger.exception("failed to roll back requirement %s", req.id)

    def _is_eligible(self, req, workspace: StudioWorkspace) -> bool:
        """Check if a requirement is eligible for design workflow execution."""
        # New designs: draft status
        if req.status == "draft":
            return True
        # Reworks: designing status with sent_back design doc
        if req.status == "designing" and req.design_doc_id:
            try:
                doc = workspace.design_docs.get(req.design_doc_id)
                return doc.status == "sent_back"
            except FileNotFoundError:
                return False
        return False
