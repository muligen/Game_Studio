# Delivery Non-Blocking Assumptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the normal blocking Delivery decision gate and replace it with automatic, documented project assumptions plus a Needs Attention escape hatch.

**Architecture:** Add a ProjectAssumption model and repository, extend the delivery planner payload with assumptions and needs-attention items, and make DeliveryPlanService save active plans directly unless a legacy gate flag is explicitly enabled. The Delivery graph injects assumptions into every task context, agents can report new assumptions in their structured output, and the Delivery board shows assumptions instead of a default decision gate column.

**Tech Stack:** Python, Pydantic, FastAPI, LangGraph, existing JSON repositories, existing Claude role adapter, React, TanStack Query.

---

## File Structure

- Create `studio/schemas/assumption.py`: `ProjectAssumption`, `ProjectAssumptionDraft`, and `NeedsAttentionItem`.
- Modify `studio/storage/workspace.py`: add `project_assumptions` and `needs_attention_items` repositories.
- Modify `studio/llm/claude_roles.py`: planner payload gets `assumptions` and `needs_attention`; delivery agent output schemas accept optional `assumptions`.
- Modify `studio/agents/delivery_planner.py`: include assumptions and needs-attention in planner output.
- Modify `studio/agents/dev.py`, `studio/agents/art.py`, `studio/agents/design.py`, `studio/agents/qa.py`, `studio/agents/quality.py`: preserve agent-reported assumptions in telemetry reports.
- Modify `studio/storage/delivery_plan_service.py`: save assumptions, skip default decision gates, add a legacy gate feature flag, append a documentation task, and expose assumptions in board data.
- Modify `studio/runtime/graph.py`: inject assumptions into task context and persist agent-reported assumptions after each task.
- Modify `studio/api/routes/delivery.py`: include assumptions and needs-attention in Delivery board response.
- Modify `web/src/lib/api.ts`: add assumption and needs-attention frontend types.
- Modify `web/src/pages/DeliveryBoard.tsx`: remove gate column for new plans and render assumptions panel.
- Create `web/src/components/board/AssumptionsPanel.tsx`: board panel for automatic decisions and blockers.
- Add tests in `tests/test_assumption_schemas.py`, `tests/test_delivery_planner_agent.py`, `tests/test_delivery_plan_service.py`, `tests/test_delivery_graph.py`, `tests/test_delivery_api.py`, and E2E coverage.

## Task 1: Add Assumption And Needs-Attention Storage

**Files:**
- Create: `studio/schemas/assumption.py`
- Modify: `studio/storage/workspace.py`
- Test: `tests/test_assumption_schemas.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_assumption_schemas.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
uv run pytest tests/test_assumption_schemas.py -q
```

Expected: fail because `studio.schemas.assumption` and the repositories are missing.

- [ ] **Step 3: Add schemas**

Create `studio/schemas/assumption.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


AssumptionSource = Literal["meeting", "planner", "agent", "acceptance"]
AssumptionCategory = Literal["product", "art", "tech", "qa", "scope", "delivery"]
AssumptionOwner = Literal["design", "dev", "qa", "art", "reviewer", "quality"]
AssumptionChangePolicy = Literal["next_iteration"]


class ProjectAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    source: AssumptionSource
    category: AssumptionCategory
    decision: StrippedNonEmptyStr
    rationale: StrippedNonEmptyStr
    impact: StrippedNonEmptyStr
    owner_agent: AssumptionOwner
    change_policy: AssumptionChangePolicy = "next_iteration"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ProjectAssumptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: AssumptionCategory
    decision: StrippedNonEmptyStr
    rationale: StrippedNonEmptyStr
    impact: StrippedNonEmptyStr
    owner_agent: AssumptionOwner
    change_policy: AssumptionChangePolicy = "next_iteration"

    def to_assumption(
        self,
        *,
        assumption_id: str,
        requirement_id: str,
        project_id: str,
        source: AssumptionSource,
    ) -> ProjectAssumption:
        return ProjectAssumption(
            id=assumption_id,
            requirement_id=requirement_id,
            project_id=project_id,
            source=source,
            category=self.category,
            decision=self.decision,
            rationale=self.rationale,
            impact=self.impact,
            owner_agent=self.owner_agent,
            change_policy=self.change_policy,
        )


class NeedsAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr | None = None
    blocker: StrippedNonEmptyStr
    evidence: list[StrippedNonEmptyStr] = Field(default_factory=list)
    recommended_action: StrippedNonEmptyStr
    affected_task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    resumable: bool = True
    status: Literal["open", "resolved"] = "open"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

- [ ] **Step 4: Add repositories to workspace**

Modify `studio/storage/workspace.py` imports:

```python
from studio.schemas.assumption import NeedsAttentionItem, ProjectAssumption
```

Inside `StudioWorkspace.__init__`, add:

```python
self.project_assumptions = JsonRepository(root / "project_assumptions", ProjectAssumption)
self.needs_attention_items = JsonRepository(root / "needs_attention_items", NeedsAttentionItem)
```

Inside `ensure_layout()`, add both roots:

```python
self.project_assumptions.root,
self.needs_attention_items.root,
```

- [ ] **Step 5: Run tests**

Run:

```powershell
uv run pytest tests/test_assumption_schemas.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add studio/schemas/assumption.py studio/storage/workspace.py tests/test_assumption_schemas.py
git commit -m "feat: add project assumption storage"
```

## Task 2: Extend Delivery Planner Payload For Assumptions

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/agents/delivery_planner.py`
- Test: `tests/test_delivery_planner_agent.py`
- Test: `tests/test_claude_roles.py`

- [ ] **Step 1: Write failing planner payload test**

Add to `tests/test_delivery_planner_agent.py`:

```python
def test_delivery_planner_payload_accepts_assumptions_and_needs_attention() -> None:
    from studio.llm import DeliveryPlannerPayload

    payload = DeliveryPlannerPayload.model_validate(
        {
            "tasks": [
                {
                    "title": "Implement Snake MVP",
                    "description": "Build the game with default retro pixel style.",
                    "owner_agent": "dev",
                    "depends_on": [],
                    "acceptance_criteria": ["Game opens in browser"],
                    "source_evidence": ["Meeting agreed browser MVP"],
                }
            ],
            "decision_gate": {"items": []},
            "assumptions": [
                {
                    "category": "art",
                    "decision": "Default to retro pixel art.",
                    "rationale": "Readable, cheap, and suitable for Snake.",
                    "impact": "Art, dev, and QA use retro pixel acceptance criteria.",
                    "owner_agent": "art",
                }
            ],
            "needs_attention": [],
        }
    )

    assert payload.assumptions[0].decision == "Default to retro pixel art."
    assert payload.needs_attention == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
uv run pytest tests/test_delivery_planner_agent.py::test_delivery_planner_payload_accepts_assumptions_and_needs_attention -q
```

Expected: fail because `DeliveryPlannerPayload` lacks `assumptions` and `needs_attention`.

- [ ] **Step 3: Add planner payload models**

In `studio/llm/claude_roles.py`, import the draft schema:

```python
from studio.schemas.assumption import ProjectAssumptionDraft
```

Add a planner needs-attention model near `DeliveryPlannerGate`:

```python
class DeliveryPlannerNeedsAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocker: str
    evidence: list[str]
    recommended_action: str
    affected_task_titles: list[str]
    resumable: bool = True
```

Extend `DeliveryPlannerPayload`:

```python
class DeliveryPlannerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[DeliveryPlannerTaskItem]
    decision_gate: DeliveryPlannerGate
    assumptions: list[ProjectAssumptionDraft] = Field(default_factory=list)
    needs_attention: list[DeliveryPlannerNeedsAttentionItem] = Field(default_factory=list)
```

Add `Field` to the existing Pydantic import in the file when needed:

```python
from pydantic import BaseModel, ConfigDict, Field
```

- [ ] **Step 4: Extend the JSON schema for Claude output**

In `_ROLE_OUTPUT_FORMATS["delivery_planner"]["properties"]`, add:

```python
"assumptions": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["product", "art", "tech", "qa", "scope", "delivery"]},
            "decision": {"type": "string"},
            "rationale": {"type": "string"},
            "impact": {"type": "string"},
            "owner_agent": {"type": "string", "enum": ["design", "dev", "qa", "art", "reviewer", "quality"]},
            "change_policy": {"type": "string", "enum": ["next_iteration"]},
        },
        "required": ["category", "decision", "rationale", "impact", "owner_agent"],
        "additionalProperties": False,
    },
},
"needs_attention": {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "blocker": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "recommended_action": {"type": "string"},
            "affected_task_titles": {"type": "array", "items": {"type": "string"}},
            "resumable": {"type": "boolean"},
        },
        "required": ["blocker", "evidence", "recommended_action", "affected_task_titles"],
        "additionalProperties": False,
    },
},
```

Update required fields:

```python
"required": ["tasks", "decision_gate", "assumptions", "needs_attention"],
```

- [ ] **Step 5: Update planner instruction text**

In `_ROLE_INSTRUCTIONS["delivery_planner"]`, replace the decision-gate-heavy wording with English text that is harder to garble:

```python
"delivery_planner": (
    "You are the Delivery planner.\n"
    "Generate a final executable task DAG from the completed meeting and requirement context.\n"
    "For normal implementation preferences that the user did not specify, choose sensible defaults, "
    "record them in assumptions, and continue. Do not create a decision gate for visual style, library choice, "
    "layout preference, level count, naming, or other ordinary implementation details.\n"
    "Use decision_gate.items only when GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE is explicitly enabled in context "
    "or the context asks for legacy decision gate behavior.\n"
    "Return JSON with tasks, decision_gate, assumptions, and needs_attention. "
    "needs_attention is only for true blockers such as missing API keys, contradictory hard constraints, "
    "unavoidable licensing risk, or unavailable external dependencies.\n"
),
```

- [ ] **Step 6: Return assumptions from DeliveryPlannerAgent**

In `studio/agents/delivery_planner.py`, update `_payload_to_dict()`:

```python
return {
    "tasks": [
        {
            "title": t.title,
            "description": t.description,
            "owner_agent": t.owner_agent,
            "depends_on": t.depends_on,
            "acceptance_criteria": t.acceptance_criteria,
            "source_evidence": t.source_evidence,
        }
        for t in payload.tasks
    ],
    "decision_gate": {
        "items": [
            {
                "question": gi.question,
                "context": gi.context,
                "options": gi.options,
                "source_evidence": gi.source_evidence,
            }
            for gi in payload.decision_gate.items
        ],
    },
    "assumptions": [item.model_dump(mode="json") for item in payload.assumptions],
    "needs_attention": [item.model_dump(mode="json") for item in payload.needs_attention],
}
```

- [ ] **Step 7: Run planner tests**

Run:

```powershell
uv run pytest tests/test_delivery_planner_agent.py tests/test_claude_roles.py -q
```

Expected: pass after updating older expected payload dictionaries to include empty `assumptions` and `needs_attention`.

- [ ] **Step 8: Commit**

```powershell
git add studio/llm/claude_roles.py studio/agents/delivery_planner.py tests/test_delivery_planner_agent.py tests/test_claude_roles.py
git commit -m "feat: add nonblocking assumptions to delivery planner"
```

## Task 3: Save Assumptions And Default To Active Plans

**Files:**
- Modify: `studio/storage/delivery_plan_service.py`
- Test: `tests/test_delivery_plan_service.py`

- [ ] **Step 1: Write tests for nonblocking plan generation**

Add to `tests/test_delivery_plan_service.py`:

```python
def test_generate_plan_saves_assumptions_and_starts_active(tmp_path: Path) -> None:
    _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
    _requirement(tmp_path)
    planner = FakePlanner(
        _planner_payload(
            gate_items=[
                {
                    "id": "visual_style",
                    "question": "Which visual style?",
                    "context": "Ordinary preference",
                    "options": ["pixel", "minimal"],
                }
            ]
        )
        | {
            "assumptions": [
                {
                    "category": "art",
                    "decision": "Default to retro pixel art.",
                    "rationale": "Readable and low-cost for Snake MVP.",
                    "impact": "Art, dev, and QA use pixel style.",
                    "owner_agent": "art",
                }
            ],
            "needs_attention": [],
        }
    )
    svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

    result = svc.generate_plan("meet_001", "proj_001")

    assert result["plan"].status == "active"
    assert result["decision_gate"] is None
    assert [task.status for task in result["tasks"]] == ["ready", "blocked", "blocked"]
    assumptions = StudioWorkspace(tmp_path).project_assumptions.list_all()
    assert assumptions[0].decision == "Default to retro pixel art."
```

The expected three tasks include the service-added documentation task from Step 4.

- [ ] **Step 2: Write test for legacy feature flag**

Add:

```python
def test_generate_plan_can_use_legacy_decision_gate_when_enabled(tmp_path: Path, monkeypatch) -> None:
    _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
    _requirement(tmp_path)
    monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
    planner = FakePlanner(
        _planner_payload(
            gate_items=[
                {
                    "id": "visual_style",
                    "question": "Which visual style?",
                    "context": "Legacy gate enabled",
                    "options": ["pixel", "minimal"],
                }
            ]
        )
        | {"assumptions": [], "needs_attention": []}
    )
    svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

    result = svc.generate_plan("meet_001", "proj_001")

    assert result["plan"].status == "awaiting_user_decision"
    assert result["decision_gate"] is not None
    assert [task.status for task in result["tasks"]] == ["preview", "preview", "preview"]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_delivery_plan_service.py::test_generate_plan_saves_assumptions_and_starts_active tests/test_delivery_plan_service.py::test_generate_plan_can_use_legacy_decision_gate_when_enabled -q
```

Expected: fail because assumptions are not saved, docs task is not appended, and gate behavior is not flag-controlled.

- [ ] **Step 4: Add helpers to DeliveryPlanService**

In `studio/storage/delivery_plan_service.py`, import `os`, assumption schemas, and `NeedsAttentionItem`:

```python
import os

from studio.schemas.assumption import NeedsAttentionItem, ProjectAssumptionDraft
```

Add helper methods inside `DeliveryPlanService`:

```python
    @staticmethod
    def _delivery_decision_gate_enabled() -> bool:
        return os.environ.get("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _save_planner_assumptions(
        self,
        *,
        requirement_id: str,
        project_id: str,
        assumptions: list[object],
    ) -> None:
        for index, raw in enumerate(assumptions, start=1):
            draft = ProjectAssumptionDraft.model_validate(raw)
            assumption = draft.to_assumption(
                assumption_id=f"assumption_{uuid4().hex}",
                requirement_id=requirement_id,
                project_id=project_id,
                source="planner",
            )
            self._ws.project_assumptions.save(assumption)

    def _save_needs_attention(
        self,
        *,
        requirement_id: str,
        project_id: str,
        plan_id: str | None,
        raw_items: list[object],
    ) -> list[NeedsAttentionItem]:
        saved: list[NeedsAttentionItem] = []
        for raw in raw_items:
            data = dict(raw) if isinstance(raw, dict) else {}
            item = NeedsAttentionItem(
                id=f"needs_{uuid4().hex}",
                requirement_id=requirement_id,
                project_id=project_id,
                plan_id=plan_id,
                blocker=str(data.get("blocker", "Delivery needs attention.")),
                evidence=[str(item) for item in data.get("evidence", [])],
                recommended_action=str(data.get("recommended_action", "Review the blocker and retry Delivery.")),
                affected_task_ids=[],
                resumable=bool(data.get("resumable", True)),
            )
            saved.append(self._ws.needs_attention_items.save(item))
        return saved
```

Add documentation task helper:

```python
    @staticmethod
    def _ensure_documentation_task(raw_tasks: list[dict[str, object]]) -> list[dict[str, object]]:
        docs_markers = ("PROJECT_BRIEF.md", "DECISIONS.md", "ACCEPTANCE.md", "RUNBOOK.md", "ITERATION_NOTES.md")
        combined = "\n".join(
            f"{task.get('title', '')}\n{task.get('description', '')}\n"
            + "\n".join(str(item) for item in task.get("acceptance_criteria", []))
            for task in raw_tasks
        )
        if all(marker in combined for marker in docs_markers):
            return raw_tasks
        titles = [str(task["title"]) for task in raw_tasks]
        return [
            *raw_tasks,
            {
                "title": "Write project delivery documentation",
                "description": (
                    "Create docs/PROJECT_BRIEF.md, docs/DECISIONS.md, docs/ACCEPTANCE.md, "
                    "docs/RUNBOOK.md, and docs/ITERATION_NOTES.md inside the target project."
                ),
                "owner_agent": "quality",
                "depends_on": titles,
                "acceptance_criteria": [
                    "docs/PROJECT_BRIEF.md explains goal, scope, gameplay, and target platform.",
                    "docs/DECISIONS.md lists confirmed decisions and automatic assumptions with rationale.",
                    "docs/ACCEPTANCE.md lists acceptance criteria and validation evidence.",
                    "docs/RUNBOOK.md explains install, run, test, and build commands.",
                    "docs/ITERATION_NOTES.md lists follow-up suggestions and assumption overrides.",
                ],
                "source_evidence": ["Delivery documentation is required for every project."],
            },
        ]
```

- [ ] **Step 5: Update `generate_plan()` behavior**

After planner output is loaded, save assumptions and needs-attention:

```python
planner_output = self._planner.generate(planning_context)
self._save_planner_assumptions(
    requirement_id=requirement.id,
    project_id=project_id,
    assumptions=list(planner_output.get("assumptions", [])),
)
raw_needs_attention = list(planner_output.get("needs_attention", []))
raw_tasks = self._ensure_documentation_task(list(planner_output.get("tasks", [])))
```

Replace:

```python
has_gate = bool(gate_items_data)
```

with:

```python
legacy_gate_enabled = self._delivery_decision_gate_enabled()
has_gate = bool(gate_items_data) and legacy_gate_enabled
```

When `raw_needs_attention` exists, create a plan with `status="cancelled"` or a new status if implemented with the acceptance plan. For this plan, keep it conservative:

```python
if raw_needs_attention:
    needs_plan_id = f"plan_{uuid4().hex}"
    plan = DeliveryPlan(
        id=needs_plan_id,
        meeting_id=meeting_id,
        requirement_id=requirement.id,
        project_id=project_id,
        status="cancelled",
    )
    self._ws.delivery_plans.save(plan)
    self._save_needs_attention(
        requirement_id=requirement.id,
        project_id=project_id,
        plan_id=plan.id,
        raw_items=raw_needs_attention,
    )
    return {"plan": plan, "tasks": [], "decision_gate": None}
```

Use `gate_items_data` only when `has_gate` is true. New plans return `decision_gate: None` unless the feature flag is on.

- [ ] **Step 6: Update existing tests for old gate behavior**

Existing tests that expect gate behavior should set:

```python
monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
```

Update test signatures to accept `monkeypatch` where needed:

```python
def test_creates_preview_tasks_when_gate_exists(
    svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
```

- [ ] **Step 7: Run service tests**

Run:

```powershell
uv run pytest tests/test_delivery_plan_service.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add studio/storage/delivery_plan_service.py tests/test_delivery_plan_service.py
git commit -m "feat: default delivery planning to nonblocking assumptions"
```

## Task 4: Inject And Persist Agent-Reported Assumptions

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/agents/dev.py`
- Modify: `studio/agents/art.py`
- Modify: `studio/agents/design.py`
- Modify: `studio/agents/qa.py`
- Modify: `studio/agents/quality.py`
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_claude_roles.py`
- Test: `tests/test_delivery_graph.py`

- [ ] **Step 1: Write output schema test**

Add to `tests/test_claude_roles.py`:

```python
def test_delivery_agent_payload_accepts_optional_assumptions() -> None:
    from studio.llm import DevPayload

    payload = DevPayload.model_validate(
        {
            "summary": "Implemented game",
            "changes": ["Added Canvas game"],
            "checks": ["npm run build passed"],
            "follow_ups": [],
            "assumptions": [
                {
                    "category": "tech",
                    "decision": "Use Canvas rendering.",
                    "rationale": "Snake MVP needs simple grid rendering.",
                    "impact": "Dev and QA validate Canvas surface.",
                    "owner_agent": "dev",
                }
            ],
        }
    )

    assert payload.assumptions[0].decision == "Use Canvas rendering."
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
uv run pytest tests/test_claude_roles.py::test_delivery_agent_payload_accepts_optional_assumptions -q
```

Expected: fail because payload models reject `assumptions`.

- [ ] **Step 3: Add optional assumptions to delivery-capable payloads**

In `studio/llm/claude_roles.py`, import:

```python
from studio.schemas.assumption import ProjectAssumptionDraft
```

Add to `DesignPayload`, `DevPayload`, `QaPayload`, `QualityPayload`, and `ArtPayload`:

```python
assumptions: list[ProjectAssumptionDraft] = Field(default_factory=list)
```

Update each corresponding output schema to include optional `assumptions` with the same item shape as Task 2. Do not add it to required lists for role outputs.

- [ ] **Step 4: Preserve assumptions in agent telemetry**

In each agent conversion method, include assumptions:

`studio/agents/dev.py`:

```python
    @staticmethod
    def _payload_to_dev_report(payload: object) -> dict[str, object]:
        return {
            "summary": payload.summary,
            "changes": payload.changes,
            "checks": payload.checks,
            "follow_ups": payload.follow_ups,
            "assumptions": [item.model_dump(mode="json") for item in getattr(payload, "assumptions", [])],
        }
```

Apply the same pattern to:

- `_payload_to_art_report`;
- `_payload_to_design_brief`;
- `_payload_to_qa_report`;
- `_payload_to_quality_report`.

Fallback patches should include `"assumptions": []`.

- [ ] **Step 5: Write graph test for assumption context and persistence**

Add to `tests/test_delivery_graph.py`:

```python
def test_delivery_graph_injects_and_persists_assumptions(tmp_path: Path, monkeypatch) -> None:
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_delivery_plan(workspace_root)
    ws = StudioWorkspace(workspace_root)
    from studio.schemas.assumption import ProjectAssumption

    ws.project_assumptions.save(
        ProjectAssumption(
            id="assumption_seed",
            requirement_id="req_001",
            project_id="proj_001",
            source="planner",
            category="art",
            decision="Default to retro pixel art.",
            rationale="Readable for Snake MVP.",
            impact="Dev uses pixel canvas style.",
            owner_agent="art",
        )
    )
    captured_goals = []

    class _Agent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state, **kwargs):
            captured_goals.append(state.goal)
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={
                    "telemetry": {
                        f"{self.role}_report": {
                            "summary": f"{self.role} done",
                            "changes": [],
                            "checks": [],
                            "follow_ups": [],
                            "assumptions": [
                                {
                                    "category": "tech",
                                    "decision": "Use Canvas for grid rendering.",
                                    "rationale": "The project is a small browser MVP.",
                                    "impact": "QA checks the canvas surface.",
                                    "owner_agent": "dev",
                                }
                            ] if self.role == "dev" else [],
                        }
                    },
                },
                trace={"node": self.role, "fallback_used": False},
            )

    class _Dispatcher:
        def get(self, node_name: str):
            return _Agent(node_name)

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)

    build_delivery_graph().invoke(
        {"workspace_root": str(workspace_root), "project_root": str(project_root), "plan_id": plan_id}
    )

    stored = StudioWorkspace(workspace_root).project_assumptions.list_all()
    assert any(item.decision == "Default to retro pixel art." for item in stored)
    assert any(item.decision == "Use Canvas for grid rendering." for item in stored)
    assert captured_goals[0]["assumptions"][0]["decision"] == "Default to retro pixel art."
```

- [ ] **Step 6: Update graph context and persistence**

In `_task_context()` in `studio/runtime/graph.py`, load assumptions:

```python
assumptions = [
    item.model_dump(mode="json")
    for item in ws.project_assumptions.list_all()
    if item.project_id == task.project_id and item.requirement_id == task.requirement_id
]
```

Add to context:

```python
"assumptions": assumptions,
"documentation_requirements": [
    "docs/PROJECT_BRIEF.md",
    "docs/DECISIONS.md",
    "docs/ACCEPTANCE.md",
    "docs/RUNBOOK.md",
    "docs/ITERATION_NOTES.md",
],
```

After agent telemetry is read in `_run_one_task()`, persist reported assumptions:

```python
reported_assumptions: list[dict[str, object]] = []
if isinstance(report, dict):
    raw_assumptions = report.get("assumptions", [])
    if isinstance(raw_assumptions, list):
        reported_assumptions = [item for item in raw_assumptions if isinstance(item, dict)]
for raw_assumption in reported_assumptions:
    draft = ProjectAssumptionDraft.model_validate(raw_assumption)
    ws.project_assumptions.save(
        draft.to_assumption(
            assumption_id=f"assumption_{uuid.uuid4().hex}",
            requirement_id=started_task.requirement_id,
            project_id=started_task.project_id,
            source="agent",
        )
    )
```

Add imports in `graph.py`:

```python
from studio.schemas.assumption import ProjectAssumptionDraft
```

`uuid` is already imported in `graph.py`, so use the existing import.

- [ ] **Step 7: Strengthen delivery prompt wording**

In `_task_context()` prompt, replace the ambiguity sentence with:

```python
"If anything is ambiguous, make the smallest reasonable assumption, continue, and include a structured assumption in your JSON if it affects product, art, tech, QA, scope, or delivery documentation.",
```

In `_prompt()` delivery execution instruction in `claude_roles.py`, mirror that sentence.

- [ ] **Step 8: Run tests**

Run:

```powershell
uv run pytest tests/test_claude_roles.py tests/test_delivery_graph.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add studio/llm/claude_roles.py studio/agents/dev.py studio/agents/art.py studio/agents/design.py studio/agents/qa.py studio/agents/quality.py studio/runtime/graph.py tests/test_claude_roles.py tests/test_delivery_graph.py
git commit -m "feat: propagate delivery assumptions to agents"
```

## Task 5: Expose Assumptions And Needs Attention In API

**Files:**
- Modify: `studio/storage/delivery_plan_service.py`
- Modify: `studio/api/routes/delivery.py`
- Test: `tests/test_delivery_api.py`

- [ ] **Step 1: Write board API test**

Add to `tests/test_delivery_api.py`:

```python
def test_delivery_board_returns_assumptions_and_needs_attention(client, workspace):
    from studio.schemas.assumption import NeedsAttentionItem, ProjectAssumption
    from studio.storage.workspace import StudioWorkspace

    ws = StudioWorkspace(workspace / ".studio-data")
    ws.ensure_layout()
    ws.project_assumptions.save(
        ProjectAssumption(
            id="assumption_001",
            requirement_id="req_001",
            project_id="proj_001",
            source="planner",
            category="art",
            decision="Default to retro pixel art.",
            rationale="Readable for Snake MVP.",
            impact="Art, dev, and QA use pixel style.",
            owner_agent="art",
        )
    )
    ws.needs_attention_items.save(
        NeedsAttentionItem(
            id="needs_001",
            requirement_id="req_001",
            project_id="proj_001",
            blocker="Missing API key.",
            evidence=["No key found."],
            recommended_action="Set the API key and retry.",
            affected_task_ids=[],
        )
    )

    resp = client.get("/api/delivery-board", params={"workspace": str(workspace), "requirement_id": "req_001"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["assumptions"][0]["decision"] == "Default to retro pixel art."
    assert data["needs_attention_items"][0]["blocker"] == "Missing API key."
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
uv run pytest tests/test_delivery_api.py::test_delivery_board_returns_assumptions_and_needs_attention -q
```

Expected: fail because board response lacks the new fields.

- [ ] **Step 3: Extend service board result**

In `DeliveryPlanService.list_board()`, load assumptions and needs-attention:

```python
assumptions = self._ws.project_assumptions.list_all()
needs_attention_items = self._ws.needs_attention_items.list_all()
```

When `requirement_id` is provided:

```python
assumptions = [item for item in assumptions if item.requirement_id == requirement_id]
needs_attention_items = [item for item in needs_attention_items if item.requirement_id == requirement_id]
```

Return them:

```python
"assumptions": assumptions,
"needs_attention_items": needs_attention_items,
```

Update `_runner_status()` to return `"needs_attention"` before active/running when open needs-attention exists. Change the signature:

```python
def _runner_status(plans, tasks, gates, needs_attention_items=None) -> str:
```

Add:

```python
if needs_attention_items and any(item.status == "open" for item in needs_attention_items):
    return "needs_attention"
```

- [ ] **Step 4: Extend API response**

In `studio/api/routes/delivery.py`, add:

```python
"assumptions": [item.model_dump() for item in result.get("assumptions", [])],
"needs_attention_items": [item.model_dump() for item in result.get("needs_attention_items", [])],
```

Extend `runner_status` handling to allow `"needs_attention"`.

- [ ] **Step 5: Run API tests**

Run:

```powershell
uv run pytest tests/test_delivery_api.py tests/test_delivery_plan_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add studio/storage/delivery_plan_service.py studio/api/routes/delivery.py tests/test_delivery_api.py tests/test_delivery_plan_service.py
git commit -m "feat: expose delivery assumptions on board"
```

## Task 6: Update Delivery Board UI

**Files:**
- Modify: `web/src/lib/api.ts`
- Create: `web/src/components/board/AssumptionsPanel.tsx`
- Modify: `web/src/pages/DeliveryBoard.tsx`

- [ ] **Step 1: Add frontend types**

Modify `web/src/lib/api.ts`:

```ts
export interface ProjectAssumption {
  id: string
  requirement_id: string
  project_id: string
  source: 'meeting' | 'planner' | 'agent' | 'acceptance'
  category: 'product' | 'art' | 'tech' | 'qa' | 'scope' | 'delivery'
  decision: string
  rationale: string
  impact: string
  owner_agent: 'design' | 'dev' | 'qa' | 'art' | 'reviewer' | 'quality'
  change_policy: 'next_iteration'
  created_at: string
}

export interface NeedsAttentionItem {
  id: string
  requirement_id: string
  project_id: string
  plan_id: string | null
  blocker: string
  evidence: string[]
  recommended_action: string
  affected_task_ids: string[]
  resumable: boolean
  status: 'open' | 'resolved'
  created_at: string
}
```

Extend `DeliveryBoard`:

```ts
assumptions: ProjectAssumption[]
needs_attention_items: NeedsAttentionItem[]
runner_status?: 'idle' | 'running' | 'waiting_for_decision' | 'failed' | 'completed' | 'needs_attention'
```

- [ ] **Step 2: Create assumptions panel component**

Create `web/src/components/board/AssumptionsPanel.tsx`:

```tsx
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { NeedsAttentionItem, ProjectAssumption } from '@/lib/api'

interface AssumptionsPanelProps {
  assumptions: ProjectAssumption[]
  needsAttentionItems: NeedsAttentionItem[]
}

export function AssumptionsPanel({ assumptions, needsAttentionItems }: AssumptionsPanelProps) {
  const openNeedsAttention = needsAttentionItems.filter((item) => item.status === 'open')

  if (assumptions.length === 0 && openNeedsAttention.length === 0) {
    return null
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {openNeedsAttention.length > 0 && (
        <Card className="p-4 border-red-300 bg-red-50">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold text-red-900">Needs Attention</h2>
            <Badge className="bg-red-200 text-red-900">{openNeedsAttention.length}</Badge>
          </div>
          <div className="mt-3 space-y-3">
            {openNeedsAttention.map((item) => (
              <div key={item.id} className="text-sm">
                <p className="font-medium text-red-950">{item.blocker}</p>
                <p className="text-red-800">{item.recommended_action}</p>
                {item.evidence.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-red-700">
                    {item.evidence.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
      {assumptions.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">Assumptions & Decisions</h2>
            <Badge variant="secondary">{assumptions.length}</Badge>
          </div>
          <div className="mt-3 grid gap-3">
            {assumptions.map((assumption) => (
              <div key={assumption.id} className="rounded-md border p-3 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant="outline">{assumption.category}</Badge>
                  <span className="text-xs text-muted-foreground">{assumption.owner_agent}</span>
                </div>
                <p className="font-medium">{assumption.decision}</p>
                <p className="mt-1 text-muted-foreground">{assumption.rationale}</p>
                <p className="mt-1 text-xs text-muted-foreground">{assumption.impact}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Render assumptions panel and hide empty gate column**

In `web/src/pages/DeliveryBoard.tsx`, import:

```tsx
import { AssumptionsPanel } from '@/components/board/AssumptionsPanel'
```

Render after `PoolStatusBar`:

```tsx
<AssumptionsPanel
  assumptions={board?.assumptions || []}
  needsAttentionItems={board?.needs_attention_items || []}
/>
```

Change the columns definition to remove the gate column from the default list:

```tsx
const TASK_COLUMNS = [
  { key: 'blocked', title: 'Blocked', status: 'blocked' },
  { key: 'ready', title: 'Ready', status: 'ready' },
  { key: 'in_progress', title: 'In Progress', status: 'in_progress' },
  { key: 'review', title: 'Review', status: 'review' },
  { key: 'done', title: 'Done', status: 'done' },
] as const
```

Keep legacy gate rendering separately only when `gates.length > 0`:

```tsx
{gates.length > 0 && (
  <div className="flex-shrink-0 w-80">
    <h2 className="font-semibold mb-4 text-sm uppercase text-gray-600">
      Legacy Decision Needed ({gates.length})
    </h2>
    <div className="space-y-3">
      {gates.map((gate) => (
        <KickoffDecisionGateCard key={gate.id} gate={gate} onResolve={() => setResolveGate(gate)} />
      ))}
    </div>
  </div>
)}
```

Map `TASK_COLUMNS` for normal task columns.

- [ ] **Step 4: Build frontend**

Run:

```powershell
cd web
npm run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add web/src/lib/api.ts web/src/components/board/AssumptionsPanel.tsx web/src/pages/DeliveryBoard.tsx
git commit -m "feat: show nonblocking delivery assumptions"
```

## Task 7: Add E2E Coverage For No-Gate Delivery

**Files:**
- Modify: `web/e2e/delivery-agent-context.spec.ts` or create `web/e2e/delivery-nonblocking-assumptions.spec.ts`
- Modify: `web/e2e/helpers/api.ts` if board response typing is duplicated there

- [ ] **Step 1: Create E2E test**

Create `web/e2e/delivery-nonblocking-assumptions.spec.ts`:

```ts
import { expect, test } from '@playwright/test'
import { createWorkspace, readJson, writeJson } from './helpers/api'

test('delivery starts with assumptions instead of a decision gate', async ({ page }) => {
  const workspace = await createWorkspace('delivery-nonblocking-assumptions')
  const requirementId = 'req_assumptions'
  const meetingId = 'meeting_assumptions'
  const planId = 'plan_assumptions'
  const taskId = 'task_docs'

  await writeJson(workspace, 'requirements', requirementId, {
    id: requirementId,
    title: 'Snake MVP',
    kind: 'mvp',
    status: 'approved',
    project_id: 'proj_assumptions',
    acceptance_criteria: ['Game opens in browser'],
  })
  await writeJson(workspace, 'meetings', meetingId, {
    id: meetingId,
    requirement_id: requirementId,
    title: 'Snake kickoff',
    status: 'completed',
    decisions: ['Build a browser Snake MVP'],
    consensus_points: ['Use a simple browser implementation'],
    pending_user_decisions: [],
  })
  await writeJson(workspace, 'delivery_plans', planId, {
    id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: 'proj_assumptions',
    status: 'active',
    task_ids: [taskId],
    decision_gate_id: null,
    decision_resolution_version: null,
  })
  await writeJson(workspace, 'delivery_tasks', taskId, {
    id: taskId,
    plan_id: planId,
    meeting_id: meetingId,
    requirement_id: requirementId,
    project_id: 'proj_assumptions',
    title: 'Write project delivery documentation',
    description: 'Create required project docs.',
    owner_agent: 'quality',
    status: 'ready',
    depends_on_task_ids: [],
    execution_result_id: null,
    output_artifact_ids: [],
    acceptance_criteria: ['docs/RUNBOOK.md explains run commands'],
    meeting_snapshot: null,
    decision_resolution_version: null,
    attempt_count: 0,
    last_error: null,
    last_failed_at: null,
  })
  await writeJson(workspace, 'project_assumptions', 'assumption_art', {
    id: 'assumption_art',
    requirement_id: requirementId,
    project_id: 'proj_assumptions',
    source: 'planner',
    category: 'art',
    decision: 'Default to retro pixel art.',
    rationale: 'Readable and low-cost for Snake MVP.',
    impact: 'Art, dev, and QA use pixel style.',
    owner_agent: 'art',
    change_policy: 'next_iteration',
  })

  await page.goto(`/delivery?workspace=${encodeURIComponent(workspace)}&requirement_id=${requirementId}`)

  await expect(page.getByText('Assumptions & Decisions')).toBeVisible()
  await expect(page.getByText('Default to retro pixel art.')).toBeVisible()
  await expect(page.getByText('Kickoff Decision Needed')).toHaveCount(0)
  await expect(page.getByText('Write project delivery documentation')).toBeVisible()
})
```

If the helper does not support `workspace` query param directly, follow the existing E2E setup pattern in `web/e2e/delivery-agent-context.spec.ts` and adapt the navigation line to that pattern.

- [ ] **Step 2: Run E2E test**

Run:

```powershell
cd web
npm run test:e2e -- delivery-nonblocking-assumptions.spec.ts
```

Expected: pass.

- [ ] **Step 3: Commit**

```powershell
git add web/e2e/delivery-nonblocking-assumptions.spec.ts web/e2e/helpers/api.ts
git commit -m "test: cover nonblocking delivery assumptions"
```

## Task 8: Final Verification

**Files:**
- All files touched above

- [ ] **Step 1: Run focused backend tests**

```powershell
uv run pytest tests/test_assumption_schemas.py tests/test_delivery_planner_agent.py tests/test_claude_roles.py tests/test_delivery_plan_service.py tests/test_delivery_graph.py tests/test_delivery_api.py -q
```

Expected: pass.

- [ ] **Step 2: Run full backend suite**

```powershell
uv run pytest -q
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

```powershell
cd web
npm run build
```

Expected: pass.

- [ ] **Step 4: Run E2E slice**

```powershell
cd web
npm run test:e2e -- delivery-nonblocking-assumptions.spec.ts
```

Expected: pass.

- [ ] **Step 5: Check git status**

```powershell
git status --short
```

Expected: only intentional files are changed before each commit, and no generated project files are tracked.

## Self-Review

- Spec coverage: assumptions, Needs Attention, planner behavior, agent behavior, board interaction, API/storage, backward compatibility, observability, and tests are mapped to implementation tasks.
- Placeholder scan: this plan uses concrete file paths, commands, snippets, status names, and expected outcomes.
- Type consistency: `ProjectAssumption`, `ProjectAssumptionDraft`, `NeedsAttentionItem`, `assumptions`, `needs_attention`, and `needs_attention_items` are used consistently.
- Delivery invariant: new plans do not block for normal decisions; ordinary ambiguity becomes structured assumptions; true blockers become Needs Attention after evidence exists.
