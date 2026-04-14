from __future__ import annotations

import pytest

from studio.domain.bug_flow import advance_bug, transition_bug
from studio.schemas.bug import BugCard


@pytest.mark.parametrize(
    ("start_status", "next_status", "prepared"),
    [
        ("new", "fixing", False),
        ("fixing", "fixed", False),
        ("fixed", "verifying", False),
        ("verifying", "closed", False),
        ("verifying", "reopened", True),
        ("verifying", "needs_user_decision", True),
        ("reopened", "fixing", False),
        ("reopened", "needs_user_decision", False),
        ("needs_user_decision", "fixing", False),
        ("needs_user_decision", "closed", False),
    ],
)
def test_bug_allows_table_transitions(start_status: str, next_status: str, prepared: bool) -> None:
    bug = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status=start_status,
        owner="qa_agent",
    )

    updated = transition_bug(bug, next_status, prepared=prepared)

    assert updated.status == next_status


@pytest.mark.parametrize(
    ("reopen_count", "expected_status", "expected_count", "requires_user_flag"),
    [
        (0, "reopened", 1, False),
        (1, "needs_user_decision", 2, True),
        (2, "needs_user_decision", 3, False),
    ],
)
def test_advance_bug_handles_reopen_transitions(
    reopen_count: int,
    expected_status: str,
    expected_count: int,
    requires_user_flag: bool,
) -> None:
    bug = BugCard(
        id="bug_002",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        reopen_count=reopen_count,
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=True, severity_requires_user=requires_user_flag)

    assert updated.status == expected_status
    assert updated.reopen_count == expected_count


def test_advance_bug_closes_when_not_reopening() -> None:
    bug = BugCard(
        id="bug_003",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=False)

    assert updated.status == "closed"


def test_transition_bug_rejects_direct_reopen_from_verifying() -> None:
    bug = BugCard(
        id="bug_004",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        owner="qa_agent",
    )

    with pytest.raises(ValueError, match="reopen bug transitions require advance_bug"):
        transition_bug(bug, "reopened")


def test_transition_bug_rejects_unprepared_needs_user_decision_from_verifying() -> None:
    bug = BugCard(
        id="bug_007",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        owner="qa_agent",
    )

    with pytest.raises(ValueError, match="reopen bug transitions require advance_bug"):
        transition_bug(bug, "needs_user_decision")


def test_bug_rejects_closed_to_fixing() -> None:
    bug = BugCard(
        id="bug_006",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="closed",
        owner="qa_agent",
    )

    with pytest.raises(ValueError, match="invalid bug transition"):
        transition_bug(bug, "fixing")
