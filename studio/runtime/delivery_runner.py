from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from studio.runtime.graph import build_delivery_graph

logger = logging.getLogger(__name__)

DeliveryRunner = Callable[[Path, Path, str], None]
_threads: set[threading.Thread] = set()
_lock = threading.Lock()


def run_delivery_plan(workspace_root: Path, project_root: Path, plan_id: str) -> None:
    """Run an active delivery plan through the LangGraph delivery runner."""
    try:
        build_delivery_graph().invoke(
            {
                "workspace_root": str(workspace_root),
                "project_root": str(project_root),
                "plan_id": plan_id,
            }
        )
    except Exception:
        logger.exception("Delivery runner failed for plan %s", plan_id)


def submit_delivery_plan(
    workspace_root: Path,
    project_root: Path,
    plan_id: str,
    *,
    runner: DeliveryRunner = run_delivery_plan,
) -> threading.Thread:
    """Start a delivery plan runner outside the HTTP request lifecycle."""

    def _target() -> None:
        try:
            runner(workspace_root, project_root, plan_id)
        finally:
            with _lock:
                _threads.discard(threading.current_thread())

    thread = threading.Thread(
        target=_target,
        name=f"delivery-runner-{plan_id}",
        daemon=True,
    )
    with _lock:
        _threads.add(thread)
    thread.start()
    return thread


def active_delivery_runner_count() -> int:
    with _lock:
        return len([thread for thread in _threads if thread.is_alive()])
