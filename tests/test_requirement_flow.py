from __future__ import annotations

import pytest

from studio.domain.requirement_flow import transition_requirement
from studio.schemas.requirement import RequirementCard


@pytest.mark.parametrize(
    ("start_status", "next_status"),
    [
        ("draft", "designing"),
        ("designing", "pending_user_review"),
        ("pending_user_review", "approved"),
        ("pending_user_review", "designing"),
        ("approved", "implementing"),
        ("implementing", "self_test_passed"),
        ("self_test_passed", "testing"),
        ("testing", "pending_user_acceptance"),
        ("testing", "implementing"),
        ("pending_user_acceptance", "quality_check"),
        ("pending_user_acceptance", "implementing"),
        ("quality_check", "done"),
        ("quality_check", "implementing"),
    ],
)
def test_requirement_allows_table_transitions(start_status: str, next_status: str) -> None:
    card = RequirementCard(id="req_001", title="Add relic system", status=start_status)

    updated = transition_requirement(card, next_status)

    assert updated.status == next_status


def test_requirement_rejects_draft_to_done() -> None:
    card = RequirementCard(id="req_001", title="Add relic system")

    with pytest.raises(ValueError, match="invalid requirement transition"):
        transition_requirement(card, "done")
