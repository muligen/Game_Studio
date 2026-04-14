from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from studio.domain.approvals import approve_design_doc, send_back_design_doc
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/design-docs", tags=["design-docs"])


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance, ensuring it exists."""
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_design_docs(workspace: str) -> list[DesignDoc]:
    """List all design docs in the workspace."""
    store = _get_workspace(workspace)
    return store.design_docs.list_all()


@router.get("/{design_id}")
async def get_design_doc(workspace: str, design_id: str) -> DesignDoc:
    """Get a specific design doc by ID."""
    store = _get_workspace(workspace)
    try:
        return store.design_docs.get(design_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Design doc not found")


@router.patch("/{design_id}")
async def update_design_doc(
    workspace: str,
    design_id: str,
    title: str | None = Body(default=None),
    summary: str | None = Body(default=None),
    core_rules: list[str] | None = Body(default=None),
    acceptance_criteria: list[str] | None = Body(default=None),
    open_questions: list[str] | None = Body(default=None),
) -> DesignDoc:
    """Update a design doc."""
    store = _get_workspace(workspace)
    doc = store.design_docs.get(design_id)

    # Build update dict with only provided fields
    updates: dict[str, object] = {}
    if title is not None:
        updates["title"] = title
    if summary is not None:
        updates["summary"] = summary
    if core_rules is not None:
        updates["core_rules"] = core_rules
    if acceptance_criteria is not None:
        updates["acceptance_criteria"] = acceptance_criteria
    if open_questions is not None:
        updates["open_questions"] = open_questions

    updated = doc.model_copy(update=updates)
    return store.design_docs.save(updated)


@router.post("/{design_id}/approve")
async def approve_design(workspace: str, design_id: str) -> dict[str, object]:
    """Approve a design doc and transition the linked requirement."""
    store = _get_workspace(workspace)
    doc = store.design_docs.get(design_id)
    requirement = store.requirements.get(doc.requirement_id)

    # Get balance tables for this requirement
    balance_tables: list[BalanceTable] = []
    for bt_id in requirement.balance_table_ids:
        try:
            balance_tables.append(store.balance_tables.get(bt_id))
        except FileNotFoundError:
            pass

    try:
        updated_doc, updated_req, logs = approve_design_doc(
            requirement, doc, balance_tables
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    store.design_docs.save(updated_doc)
    store.requirements.save(updated_req)
    for log in logs:
        store.logs.save(log)

    return {
        "design_doc": updated_doc.model_dump(),
        "requirement": updated_req.model_dump(),
    }


@router.post("/{design_id}/send-back")
async def send_back_design(
    workspace: str,
    design_id: str,
    reason: str = Body(embed=True),
) -> dict[str, object]:
    """Send back a design doc for revision."""
    store = _get_workspace(workspace)
    doc = store.design_docs.get(design_id)
    requirement = store.requirements.get(doc.requirement_id)

    try:
        updated_doc, updated_req, logs = send_back_design_doc(
            requirement, doc, reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    store.design_docs.save(updated_doc)
    store.requirements.save(updated_req)
    for log in logs:
        store.logs.save(log)

    return {
        "design_doc": updated_doc.model_dump(),
        "requirement": updated_req.model_dump(),
    }
