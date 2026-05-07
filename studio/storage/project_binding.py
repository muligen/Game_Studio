from __future__ import annotations

from typing import Iterable

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def preferred_project_id_for_requirement(
    store: StudioWorkspace,
    requirement: RequirementCard,
) -> str | None:
    """Return the project a requirement should use.

    Product MVPs use their own project records. Change requests always continue
    from the completed MVP project in the workspace.
    """
    if requirement.kind == "change_request":
        mvp_project_id = completed_mvp_project_id(store)
        if mvp_project_id:
            return mvp_project_id
    return _project_id_from_requirement_records(store, requirement)


def completed_mvp_project_id(store: StudioWorkspace) -> str | None:
    requirements = sorted(
        store.requirements.list_all(),
        key=lambda item: item.created_at,
        reverse=True,
    )
    for requirement in requirements:
        if requirement.kind != "product_mvp" or requirement.status != "done":
            continue
        project_id = _project_id_from_requirement_records(store, requirement)
        if project_id:
            return project_id
    return None


def _project_id_from_requirement_records(
    store: StudioWorkspace,
    requirement: RequirementCard,
) -> str | None:
    if requirement.project_id:
        return requirement.project_id

    plan_project = _latest_project_id(
        (
            (plan.created_at, plan.project_id)
            for plan in store.delivery_plans.list_all()
            if plan.requirement_id == requirement.id
        )
    )
    if plan_project:
        return plan_project

    kickoff_project = _latest_project_id(
        (
            ((task.updated_at or task.started_at or ""), task.project_id)
            for task in store.kickoff_tasks.list_all()
            if task.requirement_id == requirement.id
        )
    )
    if kickoff_project:
        return kickoff_project

    session_project = _latest_project_id(
        (
            (session.updated_at, session.project_id)
            for session in store.clarifications.list_all()
            if session.requirement_id == requirement.id and session.project_id
        )
    )
    return session_project


def _latest_project_id(candidates: Iterable[tuple[str, str | None]]) -> str | None:
    pairs = [(timestamp, project_id) for timestamp, project_id in candidates if project_id]
    if not pairs:
        return None
    return sorted(pairs, key=lambda item: item[0], reverse=True)[0][1]
