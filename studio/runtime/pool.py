"""Centralized thread pool for all Agent SDK calls.

Provides a single, configurable ThreadPoolExecutor that limits concurrent
LLM invocations across the system.  All callers should use ``submit()``
rather than creating their own executors.

Configuration:
    GAME_STUDIO_AGENT_POOL_SIZE – max concurrent agent workers (default 3).
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

_max_workers = int(os.environ.get("GAME_STUDIO_AGENT_POOL_SIZE", "3"))

_pool: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=_max_workers,
    thread_name_prefix="agent-worker",
)


def submit(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
    """Submit a callable to the shared agent thread pool."""
    return _pool.submit(fn, *args, **kwargs)


def shutdown(wait: bool = True) -> None:
    """Shut down the pool.  Called during application lifespan teardown."""
    logger.info("agent pool shutting down (max_workers was %d)", _max_workers)
    _pool.shutdown(wait=wait)
