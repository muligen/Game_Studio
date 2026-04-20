# Agent Meeting Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a moderator-driven LangGraph meeting graph where multiple agents (design/art/dev/qa) give structured opinions, the moderator synthesizes consensus/conflicts, and the output is a meeting minutes document.

**Architecture:** New `build_meeting_graph()` with 6 nodes. ModeratorAgent handles 4 phases via `ClaudeRoleAdapter.generate("moderator", ...)`. Fan-out uses LangGraph `Send` API for parallel agent opinions. All schemas follow existing Pydantic patterns.

**Tech Stack:** Python 3.12, LangGraph, Pydantic, Claude Agent SDK

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `studio/schemas/meeting.py` | Create | MeetingMinutes + AgentOpinion schemas |
| `studio/llm/claude_roles.py` | Modify | Add 4 moderator payload schemas + prompt templates + output formats |
| `studio/agents/moderator.py` | Create | ModeratorAgent with 4 phase methods |
| `studio/agents/profiles/moderator.yaml` | Create | Moderator agent profile |
| `.claude/agents/moderator/CLAUDE.md` | Create | Moderator Claude context |
| `studio/runtime/graph.py` | Modify | Add `build_meeting_graph()` |
| `studio/storage/workspace.py` | Modify | Add `meetings` repository |
| `studio/api/routes/meetings.py` | Create | GET endpoints for meetings |
| `studio/api/main.py` | Modify | Register meetings router |
| `tests/test_meeting_graph.py` | Create | Tests for meeting graph |

---

### Task 1: Meeting Schemas

**Files:**
- Create: `studio/schemas/meeting.py`
- Test: `tests/test_meeting_schemas.py`

- [ ] **Step 1: Write schema tests**

```python
# tests/test_meeting_schemas.py
import pytest
from pydantic import ValidationError
from studio.schemas.meeting import AgentOpinion, MeetingMinutes


def test_agent_opinion_requires_role_and_summary():
    opinion = AgentOpinion(agent_role="design", summary="Looks good")
    assert opinion.agent_role == "design"
    assert opinion.proposals == []
    assert opinion.risks == []
    assert opinion.open_questions == []


def test_agent_opinion_rejects_empty_role():
    with pytest.raises(ValidationError):
        AgentOpinion(agent_role="", summary="x")


def test_meeting_minutes_basic():
    m = MeetingMinutes(
        id="meeting_abc",
        requirement_id="req_abc",
        title="Sprint Review",
        agenda=["Scope", "Tech"],
        attendees=["design", "dev"],
        opinions=[
            AgentOpinion(agent_role="design", summary="ok"),
            AgentOpinion(agent_role="dev", summary="risky"),
        ],
        consensus_points=["Use Unity"],
        conflict_points=["Timeline"],
        supplementary={},
        decisions=["Start with MVP"],
        action_items=["Create tasks"],
        pending_user_decisions=["Approve budget"],
    )
    assert m.status == "draft"
    assert len(m.opinions) == 2


def test_meeting_minutes_rejects_extra_fields():
    with pytest.raises(ValidationError):
        MeetingMinutes(
            id="meeting_abc",
            requirement_id="req_abc",
            title="Review",
            agenda=[],
            attendees=[],
            opinions=[],
            consensus_points=[],
            conflict_points=[],
            supplementary={},
            decisions=[],
            action_items=[],
            pending_user_decisions=[],
            unknown_field="oops",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_meeting_schemas.py -v`
Expected: FAIL — `studio.schemas.meeting` does not exist

- [ ] **Step 3: Write meeting schemas**

```python
# studio/schemas/meeting.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


class AgentOpinion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_role: StrippedNonEmptyStr
    summary: StrippedNonEmptyStr
    proposals: list[StrippedNonEmptyStr] = Field(default_factory=list)
    risks: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)


MeetingStatus = Literal["draft", "completed"]


class MeetingMinutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    title: StrippedNonEmptyStr
    agenda: list[StrippedNonEmptyStr] = Field(default_factory=list)
    attendees: list[StrippedNonEmptyStr] = Field(default_factory=list)
    opinions: list[AgentOpinion] = Field(default_factory=list)
    consensus_points: list[StrippedNonEmptyStr] = Field(default_factory=list)
    conflict_points: list[StrippedNonEmptyStr] = Field(default_factory=list)
    supplementary: dict[str, str] = Field(default_factory=dict)
    decisions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    action_items: list[StrippedNonEmptyStr] = Field(default_factory=list)
    pending_user_decisions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    status: MeetingStatus = "draft"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_meeting_schemas.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add studio/schemas/meeting.py tests/test_meeting_schemas.py
git commit -m "feat: add MeetingMinutes and AgentOpinion schemas"
```

---

### Task 2: Moderator Payload Schemas and Prompts

**Files:**
- Modify: `studio/llm/claude_roles.py`

- [ ] **Step 1: Add 4 moderator payload classes** after the existing payload classes (after `WorkerPayload`)

```python
class ModeratorPreparePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agenda: list[str]
    attendees: list[str]
    focus_questions: list[str]


class AgentOpinionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    proposals: list[str]
    risks: list[str]
    open_questions: list[str]


class ModeratorSummaryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consensus_points: list[str]
    conflict_points: list[str]
    conflict_resolution_needed: list[str]


class ModeratorMinutesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    decisions: list[str]
    action_items: list[str]
    pending_user_decisions: list[str]
```

- [ ] **Step 2: Register moderator payloads in `_ROLE_PAYLOAD_MODELS`**

Add to the `_ROLE_PAYLOAD_MODELS` dict:

```python
    "moderator_prepare": ModeratorPreparePayload,
    "moderator_summary": ModeratorSummaryPayload,
    "moderator_minutes": ModeratorMinutesPayload,
    "agent_opinion": AgentOpinionPayload,
```

- [ ] **Step 3: Add moderator prompt templates** to `_ROLE_PROMPTS`

```python
    "moderator_prepare": (
        "You are the meeting moderator.\n"
        "Analyze the user's intent and the requirement context.\n"
        "Return only JSON with agenda (list of discussion topics), "
        "attendees (subset of: design, art, dev, qa), "
        "and focus_questions (specific questions for the meeting).\n"
    ),
    "moderator_summary": (
        "You are the meeting moderator.\n"
        "Given structured opinions from multiple agents, synthesize the results.\n"
        "Return only JSON with consensus_points, conflict_points, "
        "and conflict_resolution_needed (conflicts requiring supplementary discussion).\n"
    ),
    "moderator_minutes": (
        "You are the meeting moderator.\n"
        "Given all meeting context (agenda, opinions, consensus, conflicts, supplementary discussion), "
        "produce the final meeting minutes.\n"
        "Return only JSON with title, summary, decisions, action_items, "
        "and pending_user_decisions (items requiring human approval).\n"
    ),
    "agent_opinion": (
        "You are providing a professional opinion in a structured review meeting.\n"
        "Analyze the agenda and user intent from your professional perspective.\n"
        "Return only JSON with summary, proposals (concrete suggestions), "
        "risks (potential issues), and open_questions (items needing clarification).\n"
    ),
```

- [ ] **Step 4: Add moderator output format schemas** to `_ROLE_OUTPUT_FORMATS`

```python
    "moderator_prepare": {
        "type": "object",
        "properties": {
            "agenda": {"type": "array", "items": {"type": "string"}},
            "attendees": {"type": "array", "items": {"type": "string"}},
            "focus_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["agenda", "attendees", "focus_questions"],
        "additionalProperties": False,
    },
    "moderator_summary": {
        "type": "object",
        "properties": {
            "consensus_points": {"type": "array", "items": {"type": "string"}},
            "conflict_points": {"type": "array", "items": {"type": "string"}},
            "conflict_resolution_needed": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["consensus_points", "conflict_points", "conflict_resolution_needed"],
        "additionalProperties": False,
    },
    "moderator_minutes": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "decisions": {"type": "array", "items": {"type": "string"}},
            "action_items": {"type": "array", "items": {"type": "string"}},
            "pending_user_decisions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "summary", "decisions", "action_items", "pending_user_decisions"],
        "additionalProperties": False,
    },
    "agent_opinion": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "proposals": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "proposals", "risks", "open_questions"],
        "additionalProperties": False,
    },
```

- [ ] **Step 5: Run existing tests to verify nothing breaks**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add studio/llm/claude_roles.py
git commit -m "feat: add moderator and agent-opinion payload schemas and prompts"
```

---

### Task 3: Moderator Agent Profile

**Files:**
- Create: `studio/agents/profiles/moderator.yaml`
- Create: `.claude/agents/moderator/CLAUDE.md`

- [ ] **Step 1: Create moderator profile YAML**

```yaml
# studio/agents/profiles/moderator.yaml
name: moderator
enabled: true
system_prompt: Facilitate structured review meetings. Organize agenda, synthesize multi-perspective input, and produce clear decisions with action items.
claude_project_root: .claude/agents/moderator
model: sonnet
fallback_policy: default
```

- [ ] **Step 2: Create moderator Claude context**

```bash
mkdir -p .claude/agents/moderator
```

```markdown
<!-- .claude/agents/moderator/CLAUDE.md -->
This directory belongs only to the moderator agent.
```

- [ ] **Step 3: Verify profile loads**

Run: `python -c "from studio.agents.profile_loader import AgentProfileLoader; p = AgentProfileLoader().load('moderator'); print(p.name, p.system_prompt[:30])"`
Expected: `moderator Facilitate structured review`

- [ ] **Step 4: Commit**

```bash
git add studio/agents/profiles/moderator.yaml .claude/agents/moderator/CLAUDE.md
git commit -m "feat: add moderator agent profile and Claude context"
```

---

### Task 4: ModeratorAgent Class

**Files:**
- Create: `studio/agents/moderator.py`
- Test: `tests/test_moderator_agent.py`

- [ ] **Step 1: Write moderator agent tests**

```python
# tests/test_moderator_agent.py
import pytest
from unittest.mock import MagicMock, patch
from studio.agents.moderator import ModeratorAgent
from studio.schemas.runtime import RuntimeState


def _state(goal=None):
    return RuntimeState(
        project_id="meeting-project",
        run_id="run-001",
        task_id="task-001",
        goal=goal or {"prompt": "Design a puzzle game", "requirement_id": "req_001"},
    )


def test_prepare_returns_agenda_and_attendees():
    agent = ModeratorAgent(project_root=_repo_root())
    result = agent.prepare(_state())
    assert result.decision.value == "continue"
    telemetry = result.state_patch.get("telemetry", {})
    prep = telemetry.get("moderator_prepare", {})
    assert "agenda" in prep
    assert "attendees" in prep
    assert isinstance(prep["agenda"], list)
    assert isinstance(prep["attendees"], list)


def test_summarize_returns_consensus_and_conflicts():
    agent = ModeratorAgent(project_root=_repo_root())
    opinions = {
        "design": {"summary": "good", "proposals": ["x"], "risks": [], "open_questions": []},
        "dev": {"summary": "hard", "proposals": ["y"], "risks": ["perf"], "open_questions": []},
    }
    result = agent.summarize(_state(), opinions=opinions)
    telemetry = result.state_patch.get("telemetry", {})
    summary = telemetry.get("moderator_summary", {})
    assert "consensus_points" in summary
    assert "conflict_points" in summary


def test_minutes_produces_final_output():
    agent = ModeratorAgent(project_root=_repo_root())
    context = {
        "agenda": ["Game scope"],
        "opinions": {"design": {"summary": "ok"}},
        "consensus_points": ["Use 2D"],
        "conflict_points": ["Timeline tight"],
    }
    result = agent.minutes(_state(), all_context=context)
    telemetry = result.state_patch.get("telemetry", {})
    minutes = telemetry.get("moderator_minutes", {})
    assert "title" in minutes
    assert "pending_user_decisions" in minutes


def _repo_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_moderator_agent.py -v`
Expected: FAIL — `studio.agents.moderator` does not exist

- [ ] **Step 3: Write ModeratorAgent**

```python
# studio/agents/moderator.py
from __future__ import annotations

from pathlib import Path

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.schemas.runtime import NodeDecision, NodeResult, RuntimeState


class ModeratorAgent:
    def __init__(
        self,
        claude_runner: ClaudeRoleAdapter | None = None,
        project_root: Path | None = None,
    ) -> None:
        if claude_runner is not None:
            self._claude_runner = claude_runner
            return

        profile = AgentProfileLoader(repo_root=project_root).load("moderator")
        self._claude_runner = ClaudeRoleAdapter(project_root=project_root, profile=profile)

    def prepare(self, state: RuntimeState) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_prepare", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_prepare"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "prepare"}
        try:
            payload = self._claude_runner.generate("moderator_prepare", context)
            state_patch["telemetry"] = {"moderator_prepare": self._prepare_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_prepare": self._fallback_prepare(state)}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    def summarize(self, state: RuntimeState, *, opinions: dict) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_summarize", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_summarize"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "summarize", "opinions": opinions}
        try:
            payload = self._claude_runner.generate("moderator_summary", context)
            state_patch["telemetry"] = {"moderator_summary": self._summary_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_summary": self._fallback_summary()}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    def minutes(self, state: RuntimeState, *, all_context: dict) -> NodeResult:
        trace: dict[str, object] = {"node": "moderator_minutes", "llm_provider": "claude", "fallback_used": True}
        state_patch: dict[str, object] = {"plan": {"current_node": "moderator_minutes"}, "telemetry": {}}

        context = {"goal": state.goal, "phase": "minutes", **all_context}
        try:
            payload = self._claude_runner.generate("moderator_minutes", context)
            state_patch["telemetry"] = {"moderator_minutes": self._minutes_payload(payload)}
            trace["fallback_used"] = False
        except ClaudeRoleError as exc:
            trace["fallback_reason"] = str(exc)
            state_patch["telemetry"] = {"moderator_minutes": self._fallback_minutes(state)}

        return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)

    @staticmethod
    def _prepare_payload(payload: object) -> dict[str, object]:
        return {"agenda": payload.agenda, "attendees": payload.attendees, "focus_questions": payload.focus_questions}

    @staticmethod
    def _summary_payload(payload: object) -> dict[str, object]:
        return {"consensus_points": payload.consensus_points, "conflict_points": payload.conflict_points, "conflict_resolution_needed": payload.conflict_resolution_needed}

    @staticmethod
    def _minutes_payload(payload: object) -> dict[str, object]:
        return {"title": payload.title, "summary": payload.summary, "decisions": payload.decisions, "action_items": payload.action_items, "pending_user_decisions": payload.pending_user_decisions}

    @staticmethod
    def _fallback_prepare(state: RuntimeState) -> dict[str, object]:
        return {"agenda": [str(state.goal.get("prompt", ""))], "attendees": ["design", "dev", "qa"], "focus_questions": []}

    @staticmethod
    def _fallback_summary() -> dict[str, object]:
        return {"consensus_points": [], "conflict_points": [], "conflict_resolution_needed": []}

    @staticmethod
    def _fallback_minutes(state: RuntimeState) -> dict[str, object]:
        return {"title": "Meeting Notes", "summary": str(state.goal.get("prompt", "")), "decisions": [], "action_items": [], "pending_user_decisions": []}

    def consume_llm_log_entry(self) -> dict[str, object] | None:
        return self._claude_runner.consume_debug_record()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_moderator_agent.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add studio/agents/moderator.py tests/test_moderator_agent.py
git commit -m "feat: add ModeratorAgent with prepare/summarize/minutes phases"
```

---

### Task 5: Meeting Graph Definition

**Files:**
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_meeting_graph.py`

- [ ] **Step 1: Write meeting graph tests**

```python
# tests/test_meeting_graph.py
import pytest
from pathlib import Path
from studio.runtime.graph import build_meeting_graph
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def test_meeting_graph_runs_to_completion(tmp_path: Path):
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Design a puzzle game"))

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(tmp_path),
        "requirement_id": "req_001",
        "user_intent": "Design a puzzle game",
    })

    assert result["node_name"] == "moderator_minutes"
    assert "minutes" in result
    minutes = result["minutes"]
    assert minutes["requirement_id"] == "req_001"
    assert isinstance(minutes["opinions"], list)
    assert isinstance(minutes["consensus_points"], list)
    assert isinstance(minutes["pending_user_decisions"], list)


def test_meeting_graph_rejects_missing_inputs():
    graph = build_meeting_graph()
    with pytest.raises(ValueError, match="workspace_root is required"):
        graph.invoke({"requirement_id": "req_001", "user_intent": "test"})


def test_meeting_graph_saves_minutes_to_workspace(tmp_path: Path):
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Card battler"))

    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(tmp_path),
        "requirement_id": "req_001",
        "user_intent": "Card battler",
    })

    saved = workspace.meetings.get(result["minutes"]["id"])
    assert saved.requirement_id == "req_001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_meeting_graph.py -v`
Expected: FAIL — `build_meeting_graph` does not exist

- [ ] **Step 3: Add `build_meeting_graph()` to `studio/runtime/graph.py`**

Add at the end of the file, after `build_delivery_graph()`:

```python
def build_meeting_graph():
    from studio.agents.moderator import ModeratorAgent
    from studio.agents.design import DesignAgent
    from studio.agents.dev import DevAgent
    from studio.agents.qa import QaAgent
    from studio.agents.art import ArtAgent
    from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
    from studio.schemas.meeting import AgentOpinion, MeetingMinutes

    graph = StateGraph(dict)

    _AGENT_MAP = {
        "design": DesignAgent,
        "art": ArtAgent,
        "dev": DevAgent,
        "qa": QaAgent,
    }

    def moderator_prepare_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        user_intent = state.get("user_intent", "")

        workspace = StudioWorkspace(Path(workspace_root))
        requirement = workspace.requirements.get(requirement_id)
        intent = str(user_intent) if user_intent else requirement.title

        moderator = ModeratorAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-prepare-{requirement_id}",
            goal={"prompt": intent, "requirement_id": requirement_id},
        )
        result = moderator.prepare(runtime_state)
        prep = result.state_patch.get("telemetry", {}).get("moderator_prepare", {})

        return {
            **state,
            "node_name": "moderator_prepare",
            "user_intent": intent,
            "agenda": prep.get("agenda", [intent]),
            "attendees": prep.get("attendees", ["design", "dev", "qa"]),
        }

    def agent_opinion_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        target_role = state.get("_target_role", "design")
        agenda = state.get("agenda", [])
        user_intent = state.get("user_intent", "")

        agent_cls = _AGENT_MAP.get(str(target_role), DesignAgent)
        agent = agent_cls(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-{target_role}",
            goal={
                "prompt": str(user_intent),
                "phase": "opinion",
                "agenda": agenda,
                "role": str(target_role),
            },
        )
        result = agent.run(runtime_state)

        # Extract opinion from agent telemetry
        telemetry = result.state_patch.get("telemetry", {})
        report_key = next((k for k in telemetry if k.endswith("_report") or k.endswith("_brief")), None)
        report = telemetry.get(report_key, {}) if report_key else {}

        opinion = {
            "agent_role": str(target_role),
            "summary": str(report.get("summary", f"{target_role} opinion")),
            "proposals": [str(p) for p in report.get("core_rules", report.get("proposals", report.get("changes", [])))],
            "risks": [str(r) for r in report.get("open_questions", report.get("risks", []))],
            "open_questions": [str(q) for q in report.get("acceptance_criteria", report.get("open_questions", []))],
        }

        # Collect opinions into dict
        existing = dict(state.get("opinions", {}))
        existing[str(target_role)] = opinion

        return {**state, "opinions": existing}

    def moderator_summarize_node(state: dict[str, object]) -> dict[str, object]:
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")
        opinions = state.get("opinions", {})

        moderator = ModeratorAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-summarize-{requirement_id}",
            goal={"prompt": str(state.get("user_intent", "")), "requirement_id": requirement_id},
        )
        result = moderator.summarize(runtime_state, opinions=opinions)
        summary = result.state_patch.get("telemetry", {}).get("moderator_summary", {})

        return {
            **state,
            "node_name": "moderator_summarize",
            "consensus_points": summary.get("consensus_points", []),
            "conflict_points": summary.get("conflict_points", []),
        }

    def moderator_minutes_node(state: dict[str, object]) -> dict[str, object]:
        workspace_root = _require_state_str(state, "workspace_root")
        project_root = _require_state_str(state, "project_root")
        requirement_id = _require_state_str(state, "requirement_id")

        workspace = StudioWorkspace(Path(workspace_root))

        moderator = ModeratorAgent(project_root=Path(project_root))
        runtime_state = RuntimeState(
            project_id="meeting-project",
            run_id=_new_run_id(),
            task_id=f"meeting-minutes-{requirement_id}",
            goal={"prompt": str(state.get("user_intent", "")), "requirement_id": requirement_id},
        )
        all_context = {
            "agenda": state.get("agenda", []),
            "opinions": state.get("opinions", {}),
            "consensus_points": state.get("consensus_points", []),
            "conflict_points": state.get("conflict_points", []),
        }
        result = moderator.minutes(runtime_state, all_context=all_context)
        minutes_data = result.state_patch.get("telemetry", {}).get("moderator_minutes", {})

        # Build and save MeetingMinutes
        req_suffix = requirement_id.split("_")[-1]
        minutes = MeetingMinutes(
            id=f"meeting_{req_suffix}",
            requirement_id=requirement_id,
            title=str(minutes_data.get("title", "Meeting Notes")),
            summary=str(minutes_data.get("summary", "")),
            agenda=[str(a) for a in state.get("agenda", [])],
            attendees=[str(a) for a in state.get("attendees", [])],
            opinions=[
                AgentOpinion(
                    agent_role=str(op["agent_role"]),
                    summary=str(op["summary"]),
                    proposals=[str(p) for p in op.get("proposals", [])],
                    risks=[str(r) for r in op.get("risks", [])],
                    open_questions=[str(q) for q in op.get("open_questions", [])],
                )
                for op in state.get("opinions", {}).values()
            ],
            consensus_points=[str(c) for c in state.get("consensus_points", [])],
            conflict_points=[str(c) for c in state.get("conflict_points", [])],
            supplementary=state.get("supplementary", {}),
            decisions=[str(d) for d in minutes_data.get("decisions", [])],
            action_items=[str(a) for a in minutes_data.get("action_items", [])],
            pending_user_decisions=[str(d) for d in minutes_data.get("pending_user_decisions", [])],
            status="completed",
        )
        workspace.meetings.save(minutes)

        return {
            **state,
            "node_name": "moderator_minutes",
            "minutes": minutes.model_dump(),
        }

    graph.add_node("moderator_prepare", moderator_prepare_node)
    graph.add_node("agent_opinion", agent_opinion_node)
    graph.add_node("moderator_summarize", moderator_summarize_node)
    graph.add_node("moderator_minutes", moderator_minutes_node)

    graph.add_edge(START, "moderator_prepare")

    # Fan-out: send one agent_opinion invocation per attendee
    def route_to_agents(state):
        attendees = state.get("attendees", [])
        if not attendees:
            return ["moderator_summarize"]
        return [
            Send("agent_opinion", {**state, "_target_role": role})
            for role in attendees
        ]

    graph.add_conditional_edges("moderator_prepare", route_to_agents, ["agent_opinion", "moderator_summarize"])
    graph.add_edge("agent_opinion", "moderator_summarize")
    graph.add_edge("moderator_summarize", "moderator_minutes")
    graph.add_edge("moderator_minutes", END)

    return graph.compile()
```

- [ ] **Step 4: Run meeting graph tests**

Run: `pytest tests/test_meeting_graph.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run all tests to verify nothing breaks**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add studio/runtime/graph.py tests/test_meeting_graph.py
git commit -m "feat: add build_meeting_graph with fan-out agent opinions"
```

---

### Task 6: Workspace Integration

**Files:**
- Modify: `studio/storage/workspace.py`

- [ ] **Step 1: Add `meetings` repository to StudioWorkspace**

Add import and repository:

```python
from studio.schemas.meeting import MeetingMinutes
```

Add to `StudioWorkspace.__init__`:

```python
        self.meetings = JsonRepository(root / "meetings", MeetingMinutes)
```

Add `"meetings"` to `ensure_layout`:

```python
    def ensure_layout(self) -> None:
        for repo_root in (
            self.requirements.root,
            self.design_docs.root,
            self.balance_tables.root,
            self.bugs.root,
            self.logs.root,
            self.meetings.root,
        ):
            repo_root.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add studio/storage/workspace.py
git commit -m "feat: add meetings repository to StudioWorkspace"
```

---

### Task 7: Meeting API Endpoints

**Files:**
- Create: `studio/api/routes/meetings.py`
- Modify: `studio/api/main.py`

- [ ] **Step 1: Create meetings API routes**

```python
# studio/api/routes/meetings.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from studio.schemas.meeting import MeetingMinutes
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _get_workspace(workspace: str) -> StudioWorkspace:
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_meetings(workspace: str) -> list[MeetingMinutes]:
    store = _get_workspace(workspace)
    return store.meetings.list_all()


@router.get("/{meeting_id}")
async def get_meeting(workspace: str, meeting_id: str) -> MeetingMinutes:
    store = _get_workspace(workspace)
    try:
        return store.meetings.get(meeting_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")
```

- [ ] **Step 2: Register router in main.py**

Add import:

```python
from studio.api.routes import balance_tables, bugs, design_docs, logs, meetings, pool as pool_routes, requirements, workflows
```

Add router registration after existing routes:

```python
    app.include_router(meetings.router, prefix="/api")
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add studio/api/routes/meetings.py studio/api/main.py
git commit -m "feat: add meeting API endpoints for listing and fetching"
```

---

### Task 8: Register Meeting Graph in langgraph_app.py

**Files:**
- Modify: `studio/langgraph_app.py`

- [ ] **Step 1: Expose meeting_graph in langgraph_app.py**

Add import:

```python
from studio.runtime.graph import build_demo_runtime, build_delivery_graph, build_design_graph, build_meeting_graph
```

Add module-level export:

```python
meeting_graph = build_meeting_graph()
```

- [ ] **Step 2: Update langgraph.json**

Add to `graphs`:

```json
"studio_meeting_workflow": "./studio/langgraph_app.py:meeting_graph"
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add studio/langgraph_app.py langgraph.json
git commit -m "feat: register meeting_graph in langgraph_app and langgraph.json"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Each spec section maps to a task: schemas (T1), payloads (T2), profile (T3), agent (T4), graph (T5), workspace (T6), API (T7), registration (T8)
- [x] **Placeholder scan:** No TBD/TODO/placeholder steps
- [x] **Type consistency:** `AgentOpinion` schema fields match between `studio/schemas/meeting.py` and graph construction in T5; payload model names match `_ROLE_PAYLOAD_MODELS` keys in T2
