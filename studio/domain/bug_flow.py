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
    return card.model_copy(update={"status": next_status})


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
    prepared = card.model_copy(update={"reopen_count": reopen_count})
    return transition_bug(prepared, next_status)
