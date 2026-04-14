from __future__ import annotations

from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def validate_requirement_ready_for_dev(
    requirement: RequirementCard,
    design_doc: DesignDoc,
    balance_tables: list[BalanceTable],
) -> None:
    if design_doc.status != "approved":
        raise ValueError("design doc must be approved")
    if any(table.status != "approved" for table in balance_tables):
        raise ValueError("balance tables must be approved")
    if requirement.status != "approved":
        raise ValueError("requirement must be approved")
