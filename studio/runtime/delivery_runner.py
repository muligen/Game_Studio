from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from studio.runtime.graph import build_delivery_graph

logger = logging.getLogger(__name__)

DeliveryRunner = Callable[[Path, Path, str], None]
_threads: set[threading.Thread] = set()
_plan_threads: dict[str, threading.Thread] = {}
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
                current = threading.current_thread()
                _threads.discard(current)
                if _plan_threads.get(plan_id) is current:
                    del _plan_threads[plan_id]

    thread = threading.Thread(
        target=_target,
        name=f"delivery-runner-{plan_id}",
        daemon=True,
    )
    with _lock:
        existing = _plan_threads.get(plan_id)
        if existing is not None and existing.is_alive():
            return existing
        if existing is not None:
            _threads.discard(existing)
        _threads.add(thread)
        _plan_threads[plan_id] = thread
    thread.start()
    return thread


def active_delivery_runner_count() -> int:
    with _lock:
        return len([thread for thread in _threads if thread.is_alive()])
