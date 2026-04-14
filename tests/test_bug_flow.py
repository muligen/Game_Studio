from __future__ import annotations

from studio.domain.bug_flow import advance_bug, transition_bug
from studio.schemas.bug import BugCard


def test_transition_bug_allows_fixed_to_verifying() -> None:
    bug = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="Drop rate wrong",
        severity="high",
        status="fixed",
        owner="qa_agent",
    )

    updated = transition_bug(bug, "verifying")

    assert updated.status == "verifying"


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
