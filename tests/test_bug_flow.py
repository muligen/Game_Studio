from __future__ import annotations

import pytest

from studio.domain.bug_flow import advance_bug, transition_bug
from studio.schemas.bug import BugCard


@pytest.mark.parametrize(
    ("start_status", "next_status"),
    [
        ("new", "fixing"),
        ("fixing", "fixed"),
        ("fixed", "verifying"),
        ("verifying", "closed"),
        ("verifying", "reopened"),
        ("verifying", "needs_user_decision"),
        ("reopened", "fixing"),
        ("reopened", "needs_user_decision"),
        ("needs_user_decision", "fixing"),
        ("needs_user_decision", "closed"),
    ],
)
def test_bug_allows_table_transitions(start_status: str, next_status: str) -> None:
    bug = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status=start_status,
        owner="qa_agent",
    )

    updated = transition_bug(bug, next_status)

    assert updated.status == next_status


def test_advance_bug_closes_when_not_reopening() -> None:
    bug = BugCard(
        id="bug_002",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=False)

    assert updated.status == "closed"


def test_transition_bug_increments_reopen_count_for_reopened() -> None:
    bug = BugCard(
        id="bug_004",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        reopen_count=1,
        owner="qa_agent",
    )

    updated = transition_bug(bug, "reopened")

    assert updated.status == "reopened"
    assert updated.reopen_count == 2


def test_advance_bug_escalates_on_user_required_flag_before_threshold() -> None:
    bug = BugCard(
        id="bug_003",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        reopen_count=1,
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=True, severity_requires_user=True)

    assert updated.status == "needs_user_decision"
    assert updated.reopen_count == 2


def test_advance_bug_escalates_on_user_required_flag_before_threshold_with_cost_flag() -> None:
    bug = BugCard(
        id="bug_005",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        reopen_count=0,
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=True, fix_cost_requires_user=True)

    assert updated.status == "needs_user_decision"
    assert updated.reopen_count == 1


def test_bug_reopen_threshold_escalates_to_user_decision() -> None:
    bug = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="verifying",
        reopen_count=2,
        owner="qa_agent",
    )

    updated = advance_bug(bug, reopen=True)

    assert updated.status == "needs_user_decision"
    assert updated.reopen_count == 3


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
