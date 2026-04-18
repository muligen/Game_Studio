from __future__ import annotations

from fastapi import APIRouter

from studio.runtime import pool as agent_pool

router = APIRouter(prefix="/pool", tags=["pool"])


@router.get("/status")
async def get_pool_status() -> dict[str, object]:
    """Return current agent thread pool status."""
    return agent_pool.status()
