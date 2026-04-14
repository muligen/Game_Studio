from __future__ import annotations

from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.domain.approvals import (
    _ensure_balance_tables_belong_to_requirement,
    _ensure_design_doc_belongs_to_requirement,
    _ensure_required_balance_tables_present,
)


def validate_requirement_ready_for_dev(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    balance_tables: list[BalanceTable],
) -> None:
    _ensure_design_doc_belongs_to_requirement(requirement, design_doc)
    _ensure_balance_tables_belong_to_requirement(requirement, balance_tables)
    _ensure_required_balance_tables_present(requirement, balance_tables)
    if design_doc.status != "approved":
        raise ValueError("design doc must be approved")
    if any(table.status != "approved" for table in balance_tables):
        raise ValueError("balance tables must be approved")
    if requirement.status != "approved":
        raise ValueError("requirement must be approved")
