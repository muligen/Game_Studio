from __future__ import annotations

from studio.schemas.requirement import RequirementCard, RequirementStatus


_ALLOWED_TRANSITIONS: dict[RequirementStatus, set[RequirementStatus]] = {
    "draft": {"designing"},
    "designing": {"pending_user_review"},
    "pending_user_review": {"approved", "designing"},
    "approved": {"implementing", "done"},
    "implementing": {"self_test_passed", "done"},
    "self_test_passed": {"testing", "done"},
    "testing": {"pending_user_acceptance", "implementing", "done"},
    "pending_user_acceptance": {"quality_check", "implementing", "done"},
    "quality_check": {"done", "implementing"},
    "done": set(),
}


def transition_requirement(card: RequirementCard, next_status: RequirementStatus) -> RequirementCard:
    if next_status not in _ALLOWED_TRANSITIONS[card.status]:
        raise ValueError(f"invalid requirement transition: {card.status} -> {next_status}")
    return card.model_copy(update={"status": next_status})
