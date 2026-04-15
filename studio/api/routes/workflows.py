from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from studio.api.websocket import broadcast_entity_changed
from studio.domain.requirement_flow import transition_requirement
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _get_workspace(workspace: str) -> StudioWorkspace:
    """Get workspace instance."""
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


@router.post("/run-design")
async def run_design_workflow(
    workspace: str,
    requirement_id: str,
) -> dict[str, object]:
    """Run the design workflow for a requirement."""
    store = _get_workspace(workspace)

    # Get requirement with error handling
    try:
        requirement = store.requirements.get(requirement_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")

    # Transition through design states with error handling
    try:
        designing = transition_requirement(requirement, "designing")
        pending_review = transition_requirement(designing, "pending_user_review")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid state transition: {str(e)}")

    # Create design doc
    design_doc = DesignDoc(
        id=f"design_{requirement.id.split('_')[-1]}",
        requirement_id=requirement.id,
        title=f"{requirement.title} Design",
        summary=requirement.title,
        core_rules=["rule 1"],
        acceptance_criteria=["criterion 1"],
        open_questions=["question 1"],
        status="pending_user_review",
    )

    # Update requirement with design doc link
    updated_req = pending_review.model_copy(update={"design_doc_id": design_doc.id})

    store.design_docs.save(design_doc)
    store.requirements.save(updated_req)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="design_doc",
        entity_id=design_doc.id,
        action="created",
    )
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=updated_req.id,
        action="updated",
    )

    return {
        "requirement_id": updated_req.id,
        "requirement_status": updated_req.status,
        "design_doc_id": design_doc.id,
        "design_doc_status": design_doc.status,
    }


@router.post("/run-dev")
async def run_dev_workflow(
    workspace: str,
    requirement_id: str,
) -> dict[str, object]:
    """Run the dev workflow for a requirement."""
    store = _get_workspace(workspace)

    # Get requirement with error handling
    try:
        requirement = store.requirements.get(requirement_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")

    # Validate ready for dev
    from studio.domain.services import validate_requirement_ready_for_dev

    # Validate design_doc_id exists
    if not requirement.design_doc_id:
        raise HTTPException(status_code=400, detail="Requirement must have a design_doc_id to run dev workflow")

    # Get design doc with error handling
    try:
        design_doc = store.design_docs.get(requirement.design_doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design doc {requirement.design_doc_id} not found")

    # Get balance tables with error handling - skip missing ones
    balance_tables = []
    for bt_id in requirement.balance_table_ids:
        try:
            balance_tables.append(store.balance_tables.get(bt_id))
        except FileNotFoundError:
            # Skip missing balance tables gracefully
            continue

    try:
        validate_requirement_ready_for_dev(requirement, design_doc, balance_tables)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Transition to implementing with error handling
    try:
        implementing = transition_requirement(requirement, "implementing")
        self_test_passed = transition_requirement(implementing, "self_test_passed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid state transition: {str(e)}")

    updated = store.requirements.save(self_test_passed)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=updated.id,
        action="updated",
    )

    return {
        "requirement_id": updated.id,
        "status": updated.status,
    }


@router.post("/run-qa")
async def run_qa_workflow(
    workspace: str,
    requirement_id: str,
    fail: bool = False,
) -> dict[str, object]:
    """Run the QA workflow for a requirement."""
    store = _get_workspace(workspace)

    # Get requirement with error handling
    try:
        requirement = store.requirements.get(requirement_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Requirement {requirement_id} not found")

    # Transition to testing with error handling
    try:
        testing = transition_requirement(requirement, "testing")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid state transition: {str(e)}")

    if not fail:
        # Pass and go to user acceptance
        accepted = transition_requirement(testing, "pending_user_acceptance")
        updated = store.requirements.save(accepted)
        await broadcast_entity_changed(
            workspace=workspace,
            entity_type="requirement",
            entity_id=updated.id,
            action="updated",
        )
        return {
            "requirement_id": updated.id,
            "status": updated.status,
        }

    # Fail: create bug and go back to implementing
    from uuid import uuid4

    implementing = transition_requirement(testing, "implementing")
    bug_id = f"bug_{uuid4().hex[:8]}"

    from studio.schemas.bug import BugCard

    bug = BugCard(
        id=bug_id,
        requirement_id=requirement_id,
        title=f"QA failure for {requirement_id}",
        severity="high",
        owner="qa_agent",
        repro_steps=["Generated by QA"],
    )

    updated_req = implementing.model_copy(
        update={"bug_ids": [*implementing.bug_ids, bug_id]}
    )

    store.bugs.save(bug)
    store.requirements.save(updated_req)
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="bug",
        entity_id=bug.id,
        action="created",
    )
    await broadcast_entity_changed(
        workspace=workspace,
        entity_type="requirement",
        entity_id=updated_req.id,
        action="updated",
    )

    return {
        "requirement_id": updated_req.id,
        "status": updated_req.status,
        "bug_id": bug_id,
    }
