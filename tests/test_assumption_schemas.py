from __future__ import annotations

from studio.schemas.assumption import NeedsAttentionItem, ProjectAssumption, ProjectAssumptionDraft
from studio.storage.workspace import StudioWorkspace


def test_project_assumption_persists(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()

    assumption = ProjectAssumption(
        id="assumption_001",
        requirement_id="req_001",
        project_id="proj_001",
        source="planner",
        category="art",
        decision="Default to retro pixel art.",
        rationale="Snake MVP benefits from simple readable visuals.",
        impact="Art, dev, and QA tasks use retro pixel acceptance criteria.",
        owner_agent="art",
        change_policy="next_iteration",
    )
    ws.project_assumptions.save(assumption)

    loaded = ws.project_assumptions.get("assumption_001")
    assert loaded.decision == "Default to retro pixel art."
    assert loaded.category == "art"


def test_assumption_draft_can_materialize_with_ids():
    draft = ProjectAssumptionDraft(
        category="tech",
        decision="Use Vite, React, and Canvas.",
        rationale="The project is a browser game and this stack is already supported.",
        impact="Development and runbook tasks use npm scripts.",
        owner_agent="dev",
    )

    assumption = draft.to_assumption(
        assumption_id="assumption_tech",
        requirement_id="req_001",
        project_id="proj_001",
        source="planner",
    )

    assert assumption.id == "assumption_tech"
    assert assumption.change_policy == "next_iteration"


def test_needs_attention_item_persists(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    item = NeedsAttentionItem(
        id="needs_001",
        requirement_id="req_001",
        project_id="proj_001",
        plan_id="plan_001",
        blocker="Missing required external API key.",
        evidence=["No API key was present in project config."],
        recommended_action="Provide an API key and retry Delivery.",
        affected_task_ids=["task_001"],
        resumable=True,
    )
    ws.needs_attention_items.save(item)

    assert ws.needs_attention_items.get("needs_001").resumable is True
