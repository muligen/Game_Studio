from __future__ import annotations

from studio.schemas.bug import BugCard, BugStatus


_BUG_TRANSITIONS: dict[BugStatus, set[BugStatus]] = {
    "new": {"fixing"},
    "fixing": {"fixed"},
    "fixed": {"verifying"},
    "verifying": {"closed", "reopened", "needs_user_decision"},
    "reopened": {"fixing", "needs_user_decision"},
    "needs_user_decision": {"fixing", "closed"},
    "closed": set(),
}


def transition_bug(card: BugCard, next_status: BugStatus) -> BugCard:
    if next_status not in _BUG_TRANSITIONS[card.status]:
        raise ValueError(f"invalid bug transition: {card.status} -> {next_status}")
    updates: dict[str, object] = {"status": next_status}
    if next_status in {"reopened", "needs_user_decision"}:
        updates["reopen_count"] = card.reopen_count + 1
    return card.model_copy(update=updates)


def advance_bug(
    card: BugCard,
    *,
    reopen: bool = False,
    severity_requires_user: bool = False,
    fix_cost_requires_user: bool = False,
    ux_risk_requires_user: bool = False,
) -> BugCard:
    if not reopen:
        return transition_bug(card, "closed")

    reopen_count = card.reopen_count + 1
    needs_user = (
        reopen_count >= 3
        or severity_requires_user
        or fix_cost_requires_user
        or ux_risk_requires_user
    )
    next_status: BugStatus = "needs_user_decision" if needs_user else "reopened"
    return transition_bug(card, next_status)
