"""Centralized thread pool for all Agent SDK calls.

Provides a single, configurable ThreadPoolExecutor that limits concurrent
LLM invocations across the system.  All callers should use ``submit_agent()``
rather than creating their own executors.

Configuration:
    GAME_STUDIO_AGENT_POOL_SIZE – max concurrent agent workers (default 3).
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

_max_workers = int(os.environ.get("GAME_STUDIO_AGENT_POOL_SIZE", "3"))

_pool: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=_max_workers,
    thread_name_prefix="agent-worker",
)

_lock = threading.Lock()
_active_tasks: dict[str, ActiveTask] = {}


@dataclass
class ActiveTask:
    task_id: str
    agent_type: str
    requirement_id: str
    requirement_title: str = ""


def submit_agent(
    agent_type: str,
    requirement_id: str,
    requirement_title: str,
    fn: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Future[Any]:
    """Submit a callable to the shared agent thread pool with tracking."""
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = ActiveTask(
        task_id=task_id,
        agent_type=agent_type,
        requirement_id=requirement_id,
        requirement_title=requirement_title,
    )

    with _lock:
        _active_tasks[task_id] = task

    def _wrapped() -> Any:
        try:
            return fn(*args, **kwargs)
        finally:
            with _lock:
                _active_tasks.pop(task_id, None)
            _notify_status_changed()

    return _pool.submit(_wrapped)


def status() -> dict[str, Any]:
    """Return current pool status for monitoring."""
    with _lock:
        tasks = [
            {
                "task_id": t.task_id,
                "agent_type": t.agent_type,
                "requirement_id": t.requirement_id,
                "requirement_title": t.requirement_title,
            }
            for t in _active_tasks.values()
        ]
    return {
        "max_workers": _max_workers,
        "active_count": len(tasks),
        "idle": len(tasks) == 0,
        "tasks": tasks,
    }


def shutdown(wait: bool = True) -> None:
    """Shut down the pool.  Called during application lifespan teardown."""
    logger.info("agent pool shutting down (max_workers was %d)", _max_workers)
    _pool.shutdown(wait=wait)


def _notify_status_changed() -> None:
    """Fire-and-forget broadcast of pool status via WebSocket."""
    try:
        import asyncio

        from studio.api.websocket import broadcast_entity_changed

        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    if loop.is_running():
        asyncio.ensure_future(
            broadcast_entity_changed(
                workspace=".studio-data",
                entity_type="pool",
                entity_id="status",
                action="updated",
            )
        )
