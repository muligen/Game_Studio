from __future__ import annotations

import pytest

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.requirement import RequirementCard


def test_requirement_allows_pending_review_to_approved() -> None:
    card = RequirementCard(id="req_001", title="Add relic system", status="pending_user_review")

    updated = transition_requirement(card, "approved")

    assert updated.status == "approved"


def test_requirement_rejects_draft_to_done() -> None:
    card = RequirementCard(id="req_001", title="Add relic system")

    with pytest.raises(ValueError, match="invalid requirement transition"):
        transition_requirement(card, "done")
