from __future__ import annotations

from studio.domain.bug_flow import advance_bug
from studio.schemas.bug import BugCard


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
