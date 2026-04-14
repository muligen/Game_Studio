from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


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
    updated_doc = design_doc.model_copy(update={"status": "sent_back"})
    updated_requirement = transition_requirement(requirement, "designing")
    return updated_doc, updated_requirement, [
        _log("send_back", "design_doc", design_doc.id, reason)
    ]
