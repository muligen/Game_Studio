from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def _ensure_reviewable_design_doc(design_doc: DesignDoc) -> None:
    if design_doc.status != "pending_user_review":
        raise ValueError("design doc must be pending_user_review")


def _ensure_design_doc_belongs_to_requirement(
    requirement: RequirementCard,
    design_doc: DesignDoc,
) -> None:
    if design_doc.requirement_id != requirement.id:
        raise ValueError("design doc must belong to requirement")


def _ensure_balance_tables_belong_to_requirement(
    requirement: RequirementCard,
    balance_tables: list[BalanceTable],
) -> None:
    for table in balance_tables:
        if table.requirement_id != requirement.id:
            raise ValueError("balance table must belong to requirement")


def _ensure_required_balance_tables_present(
    requirement: RequirementCard,
    balance_tables: list[BalanceTable],
) -> None:
    required_ids = set(requirement.balance_table_ids)
    if not required_ids:
        return
    provided_ids = {table.id for table in balance_tables}
    missing_ids = sorted(required_ids - provided_ids)
    if missing_ids:
        raise ValueError(f"missing required balance tables: {', '.join(missing_ids)}")


def _log(action: str, target_type: str, target_id: str, message: str) -> ActionLog:
    return ActionLog(
        id=f"log_{uuid4().hex}",
        timestamp=datetime.now(UTC),
        actor="user",
        action=action,
        target_type=target_type,
        target_id=target_id,
        message=message,
        metadata={},
    )


def approve_design_doc(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    balance_tables: list[BalanceTable],
) -> tuple[DesignDoc, RequirementCard, list[ActionLog]]:
    _ensure_reviewable_design_doc(design_doc)
    _ensure_design_doc_belongs_to_requirement(requirement, design_doc)
    _ensure_balance_tables_belong_to_requirement(requirement, balance_tables)
    _ensure_required_balance_tables_present(requirement, balance_tables)
    if any(table.status != "approved" for table in balance_tables):
        raise ValueError("all balance tables must be approved")

    updated_doc = design_doc.model_copy(update={"status": "approved"})
    updated_requirement = transition_requirement(requirement, "approved")
    return updated_doc, updated_requirement, [
        _log("approve", "design_doc", design_doc.id, "approved design doc")
    ]


def send_back_design_doc(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    reason: str,
) -> tuple[DesignDoc, RequirementCard, list[ActionLog]]:
    _ensure_reviewable_design_doc(design_doc)
    _ensure_design_doc_belongs_to_requirement(requirement, design_doc)
    updated_doc = design_doc.model_copy(update={"status": "sent_back"})
    updated_requirement = transition_requirement(requirement, "designing")
    return updated_doc, updated_requirement, [
        _log("send_back", "design_doc", design_doc.id, reason)
    ]
