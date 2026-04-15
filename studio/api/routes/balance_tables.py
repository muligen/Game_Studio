from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from studio.schemas.balance_table import BalanceTable, BalanceTableRow
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/balance-tables", tags=["balance-tables"])


class UpdateBalanceTableRequest(BaseModel):
    """Request model for updating a balance table."""

    rows: list[dict[str, object]] | None = None
    locked_cells: list[str] | None = None


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance."""
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_balance_tables(workspace: str) -> list[BalanceTable]:
    """List all balance tables."""
    store = _get_workspace(workspace)
    return store.balance_tables.list_all()


@router.post("")
async def create_balance_table(
    workspace: str,
    requirement_id: str,
    table_name: str,
) -> BalanceTable:
    """Create a new balance table."""
    from uuid import uuid4

    store = _get_workspace(workspace)
    store.ensure_layout()

    table_id = f"balance_{uuid4().hex[:8]}"
    table = BalanceTable(
        id=table_id,
        requirement_id=requirement_id,
        table_name=table_name,
    )
    return store.balance_tables.save(table)


@router.get("/{table_id}")
async def get_balance_table(workspace: str, table_id: str) -> BalanceTable:
    """Get a specific balance table."""
    store = _get_workspace(workspace)
    try:
        return store.balance_tables.get(table_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Balance table not found")


@router.patch("/{table_id}")
async def update_balance_table(
    workspace: str,
    table_id: str,
    request: UpdateBalanceTableRequest,
) -> BalanceTable:
    """Update a balance table."""
    store = _get_workspace(workspace)
    table = store.balance_tables.get(table_id)

    updates: dict[str, object] = {}
    if request.rows is not None:
        # Convert dict rows to BalanceTableRow objects
        try:
            updates["rows"] = [BalanceTableRow(**r) for r in request.rows]
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if request.locked_cells is not None:
        updates["locked_cells"] = request.locked_cells

    updated = table.model_copy(update=updates)
    try:
        return store.balance_tables.save(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
