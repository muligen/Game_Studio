from __future__ import annotations

from datetime import UTC

import pytest

from studio.domain.approvals import approve_design_doc, send_back_design_doc
from studio.domain.services import validate_requirement_ready_for_dev
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def test_approving_design_doc_moves_requirement_to_approved() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )

    updated_doc, updated_requirement, logs = approve_design_doc(requirement, doc, [])

    assert updated_doc.status == "approved"
    assert updated_requirement.status == "approved"
    assert len(logs) == 1
    assert logs[0].action == "approve"
    assert logs[0].actor == "user"
    assert logs[0].target_type == "design_doc"
    assert logs[0].target_id == "design_001"
    assert logs[0].timestamp.tzinfo == UTC


def test_approve_design_doc_rejects_unapproved_balance_tables() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    table = BalanceTable(
        id="bt_001",
        requirement_id="req_001",
        table_name="relic_stats",
        status="pending_user_review",
    )

    with pytest.raises(ValueError, match="all balance tables must be approved"):
        approve_design_doc(requirement, doc, [table])


def test_approve_design_doc_rejects_foreign_design_doc() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_002",
        requirement_id="req_999",
        title="Foreign design",
        summary="Foreign",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )

    with pytest.raises(ValueError, match="design doc must belong to requirement"):
        approve_design_doc(requirement, doc, [])


def test_approve_design_doc_rejects_missing_required_balance_tables() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
        balance_table_ids=["bt_001", "bt_002"],
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    tables = [
        BalanceTable(
            id="bt_001",
            requirement_id="req_001",
            table_name="relic_stats",
            status="approved",
        )
    ]

    with pytest.raises(ValueError, match="missing required balance tables: bt_002"):
        approve_design_doc(requirement, doc, tables)


def test_approve_design_doc_rejects_foreign_balance_table() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
        balance_table_ids=["bt_001"],
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )
    table = BalanceTable(
        id="bt_001",
        requirement_id="req_999",
        table_name="relic_stats",
        status="approved",
    )

    with pytest.raises(ValueError, match="balance table must belong to requirement"):
        approve_design_doc(requirement, doc, [table])


def test_send_back_design_doc_returns_requirement_to_designing() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )

    updated_doc, updated_requirement, logs = send_back_design_doc(
        requirement,
        doc,
        "missing edge cases",
    )

    assert updated_doc.status == "sent_back"
    assert updated_requirement.status == "designing"
    assert len(logs) == 1
    assert logs[0].action == "send_back"
    assert logs[0].actor == "user"
    assert logs[0].message == "missing edge cases"
    assert logs[0].timestamp.tzinfo == UTC


def test_approve_design_doc_rejects_invalid_status() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="draft",
    )

    with pytest.raises(ValueError, match="design doc must be pending_user_review"):
        approve_design_doc(requirement, doc, [])


def test_send_back_design_doc_rejects_invalid_status() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="pending_user_review",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="approved",
    )

    with pytest.raises(ValueError, match="design doc must be pending_user_review"):
        send_back_design_doc(requirement, doc, "missing edge cases")


def test_requirement_cannot_enter_implementing_without_approved_design() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="approved",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="pending_user_review",
    )

    with pytest.raises(ValueError, match="design doc must be approved"):
        validate_requirement_ready_for_dev(requirement, doc, [])


def test_validate_requirement_ready_for_dev_rejects_foreign_design_doc() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="approved",
        design_doc_id="design_001",
    )
    doc = DesignDoc(
        id="design_002",
        requirement_id="req_999",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="approved",
    )

    with pytest.raises(ValueError, match="design doc must belong to requirement"):
        validate_requirement_ready_for_dev(requirement, doc, [])


def test_validate_requirement_ready_for_dev_rejects_missing_required_balance_tables() -> None:
    requirement = RequirementCard(
        id="req_001",
        title="Add relic system",
        status="approved",
        design_doc_id="design_001",
        balance_table_ids=["bt_001", "bt_002"],
    )
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Relic design",
        summary="Add relics",
        core_rules=[],
        acceptance_criteria=[],
        open_questions=[],
        status="approved",
    )
    tables = [
        BalanceTable(
            id="bt_001",
            requirement_id="req_001",
            table_name="relic_stats",
            status="approved",
        )
    ]

    with pytest.raises(ValueError, match="missing required balance tables: bt_002"):
        validate_requirement_ready_for_dev(requirement, doc, tables)
