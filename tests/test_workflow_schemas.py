from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard


def test_requirement_card_maps_workflow_fields() -> None:
    card = RequirementCard(
        id="req-001",
        title="Combat loop",
        type="feature",
        priority="high",
        status="open",
        owner="design",
        design_doc_id="doc-001",
        balance_table_ids=["bt-001", "bt-002"],
        bug_ids=["bug-001"],
        notes=["needs tuning"],
    )

    assert card.title == "Combat loop"
    assert card.balance_table_ids == ["bt-001", "bt-002"]


def test_requirement_card_defaults_workflow_fields() -> None:
    card = RequirementCard(
        id="req-002",
        title="Traversal",
        design_doc_id=None,
    )

    assert card.type == "requirement"
    assert card.priority == "medium"
    assert card.status == "draft"
    assert card.owner == "design_agent"
    assert card.design_doc_id is None
    assert card.balance_table_ids == []
    assert card.bug_ids == []
    assert card.notes == []


def test_design_doc_maps_workflow_fields() -> None:
    doc = DesignDoc(
        id="doc-001",
        requirement_id="req-001",
        title="Combat Loop Design",
        summary="Core loop overview",
        core_rules=["attack", "defend"],
        acceptance_criteria=["player can win"],
        open_questions=["difficulty curve"],
        status="draft",
    )

    assert doc.requirement_id == "req-001"
    assert doc.core_rules == ["attack", "defend"]
    assert doc.status == "draft"


def test_balance_table_maps_workflow_fields() -> None:
    table = BalanceTable(
        id="bt-001",
        requirement_id="req-001",
        table_name="enemy_stats",
        columns=["enemy", "hp"],
        rows=[["slime", "10"]],
        locked_cells=["A1"],
    )

    assert table.table_name == "enemy_stats"
    assert table.rows == [["slime", "10"]]
    assert table.status == "draft"


def test_bug_card_maps_workflow_fields() -> None:
    bug = BugCard(
        id="bug-001",
        requirement_id="req-001",
        title="Enemy spawns off-grid",
        severity="medium",
        status="open",
        reopen_count=2,
        owner="qa",
        repro_steps=["start match", "wait"],
        notes=["seen in build 12"],
    )

    assert bug.reopen_count == 2
    assert bug.repro_steps == ["start match", "wait"]


def test_bug_card_rejects_negative_reopen_count() -> None:
    with pytest.raises(ValidationError):
        BugCard(
            id="bug-002",
            requirement_id="req-001",
            title="Enemy spawns off-grid",
            severity="medium",
            status="new",
            reopen_count=-1,
            owner="qa",
        )


def test_action_log_uses_timestamp_and_metadata() -> None:
    timestamp = datetime(2026, 4, 14, 8, 0, tzinfo=UTC)
    log = ActionLog(
        id="log-001",
        timestamp=timestamp,
        actor="designer",
        action="created",
        target_type="requirement",
        target_id="req-001",
        message="Created requirement card",
        metadata={"source": "manual"},
    )

    assert log.timestamp == timestamp
    assert log.target_id == "req-001"
    assert log.metadata == {"source": "manual"}


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (
            RequirementCard,
            {
                "id": "req-001",
                "title": "Combat loop",
                "type": "feature",
                "priority": "high",
                "status": "open",
                "owner": "design",
                "design_doc_id": "doc-001",
                "balance_table_ids": [],
                "bug_ids": [],
                "notes": [],
                "unexpected": True,
            },
        ),
        (
            DesignDoc,
            {
                "id": "doc-001",
                "requirement_id": "req-001",
                "title": "Combat Loop Design",
                "summary": "Core loop overview",
                "core_rules": [],
                "acceptance_criteria": [],
                "open_questions": [],
                "status": "draft",
                "unexpected": True,
            },
        ),
        (
            BalanceTable,
            {
                "id": "bt-001",
                "requirement_id": "req-001",
                "table_name": "enemy_stats",
                "columns": [],
                "rows": [],
                "locked_cells": [],
                "status": "review",
                "unexpected": True,
            },
        ),
        (
            BugCard,
            {
                "id": "bug-001",
                "requirement_id": "req-001",
                "title": "Enemy spawns off-grid",
                "severity": "medium",
                "status": "open",
                "reopen_count": 0,
                "owner": "qa",
                "repro_steps": [],
                "notes": [],
                "unexpected": True,
            },
        ),
        (
            ActionLog,
            {
                "id": "log-001",
                "timestamp": datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
                "actor": "designer",
                "action": "created",
                "target_type": "requirement",
                "target_id": "req-001",
                "message": "Created requirement card",
                "metadata": {},
                "unexpected": True,
            },
        ),
    ],
)
def test_workflow_schemas_reject_extra_fields(model: type, kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as exc:
        model(**kwargs)

    assert "extra" in str(exc.value).lower()
