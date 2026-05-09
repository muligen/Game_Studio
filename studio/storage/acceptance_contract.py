from __future__ import annotations

import re

from studio.schemas.acceptance import AcceptanceContract, AcceptanceCriterion
from studio.storage.workspace import StudioWorkspace


_SYSTEM_CRITERIA: list[tuple[str, list[str], str]] = [
    ("The project exposes a detectable command to start or preview the game.", ["command"], "dev"),
    ("The project builds successfully when a build command exists.", ["command"], "dev"),
    ("The project tests pass when a test command exists.", ["command"], "qa"),
    ("The browser page opens without fatal page errors.", ["playwright", "pageerror"], "dev"),
    ("The browser console has no fatal runtime errors.", ["console"], "dev"),
    ("The page renders a visible game surface and is not blank.", ["playwright", "screenshot"], "qa"),
]


def build_acceptance_contract(ws: StudioWorkspace, plan_id: str) -> AcceptanceContract:
    plan = ws.delivery_plans.get(plan_id)
    requirement = ws.requirements.get(plan.requirement_id)
    meeting = ws.meetings.get(plan.meeting_id)
    raw_items: list[tuple[str, str, list[str], str, str]] = []

    for criterion in requirement.acceptance_criteria:
        raw_items.append(("requirement", str(criterion), ["llm"], "major", "qa"))

    for decision in meeting.decisions:
        raw_items.append(("meeting_decision", str(decision), ["llm"], "minor", "qa"))

    for consensus in meeting.consensus_points:
        raw_items.append(("meeting_consensus", str(consensus), ["llm"], "minor", "qa"))

    if plan.decision_gate_id:
        gate = ws.decision_gates.get(plan.decision_gate_id)
        for item in gate.items:
            if item.resolution:
                raw_items.append(
                    (
                        "kickoff_decision",
                        f"Kickoff decision resolved: {item.question} -> {item.resolution}",
                        ["llm"],
                        "major",
                        "qa",
                    )
                )

    for task_id in plan.task_ids:
        task = ws.delivery_tasks.get(task_id)
        if task.kind == "bug_fix":
            continue
        for criterion in task.acceptance_criteria:
            raw_items.append((f"task:{task.id}", str(criterion), ["llm"], "minor", str(task.owner_agent)))

    for text, evidence_types, owner_hint in _SYSTEM_CRITERIA:
        raw_items.append(("system", text, evidence_types, "blocker", owner_hint))

    seen: set[str] = set()
    criteria: list[AcceptanceCriterion] = []
    for source, text, evidence_types, severity, owner_hint in raw_items:
        normalized = " ".join(text.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        criteria.append(
            AcceptanceCriterion(
                id=f"crit_{len(criteria) + 1:03d}_{_slug(normalized)}",
                source=source,
                text=normalized,
                required_evidence_types=evidence_types,
                severity=severity,
                owner_hint=_owner_hint(owner_hint),
            )
        )

    return AcceptanceContract(
        id=f"contract_{plan.id}",
        plan_id=plan.id,
        requirement_id=plan.requirement_id,
        project_id=plan.project_id,
        criteria=criteria,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug[:40] or "criterion"


def _owner_hint(value: str) -> str:
    return value if value in {"dev", "art", "qa", "reviewer", "quality"} else "qa"
