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
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

_max_workers = int(os.environ.get("GAME_STUDIO_AGENT_POOL_SIZE", "3"))

_pool: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=_max_workers,
    thread_name_prefix="agent-worker",
)

_lock = threading.Lock()
_active_tasks: dict[str, ActiveTask] = {}
_recent_errors: deque[dict[str, object]] = deque(maxlen=50)


@dataclass
class ActiveTask:
    task_id: str
    agent_type: str
    requirement_id: str
    requirement_title: str = ""
    started_at: str = ""


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
        started_at=datetime.now(timezone.utc).isoformat(),
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
    now = datetime.now(timezone.utc)
    with _lock:
        tracked = len(_active_tasks)
        tasks = []
        for t in _active_tasks.values():
            task_dict: dict[str, Any] = {
                "task_id": t.task_id,
                "agent_type": t.agent_type,
                "requirement_id": t.requirement_id,
                "requirement_title": t.requirement_title,
                "started_at": t.started_at,
            }
            if t.started_at:
                try:
                    started = datetime.fromisoformat(t.started_at)
                    task_dict["running_duration_seconds"] = (now - started).total_seconds()
                except (ValueError, TypeError):
                    task_dict["running_duration_seconds"] = 0.0
            else:
                task_dict["running_duration_seconds"] = 0.0
            tasks.append(task_dict)
        errors = list(_recent_errors)
    running = len(getattr(_pool, "_threads", set()))
    return {
        "max_workers": _max_workers,
        "active_count": running,
        "queued_count": max(0, tracked - running),
        "idle": tracked == 0,
        "tasks": tasks,
        "recent_errors": errors,
    }


def shutdown(wait: bool = True) -> None:
    """Shut down the pool.  Called during application lifespan teardown."""
    logger.info("agent pool shutting down (max_workers was %d)", _max_workers)
    _pool.shutdown(wait=wait)


def record_task_error(
    task_id: str,
    agent_type: str,
    requirement_id: str,
    error_type: str,
    error_message: str,
) -> None:
    """Record a task error so monitoring dashboards can surface it."""
    with _lock:
        _recent_errors.append({
            "task_id": task_id,
            "agent_type": agent_type,
            "requirement_id": requirement_id,
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    _notify_status_changed()


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
