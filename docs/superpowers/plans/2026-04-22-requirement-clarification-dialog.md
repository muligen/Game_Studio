# Requirement Clarification Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a web dialog where the user clarifies a draft requirement with an agent, producing structured `meeting_context` for kickoff.

**Architecture:** A `RequirementClarificationSession` schema stores conversation + structured context draft in workspace. A new `requirement_clarifier` agent role returns both a reply and a `RequirementClarifierPayload`. Three API endpoints handle session lifecycle (start, message, kickoff). The kickoff endpoint creates project-agent sessions via `SessionRegistry`, invokes Meeting Graph with `meeting_context`, and returns `project_id`. Frontend adds a dialog component and "Clarify" button on draft requirement cards.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, React, TypeScript, TanStack Query, shadcn/ui

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `studio/schemas/clarification.py` | Create | `ClarificationMessage`, `MeetingContextDraft`, `ReadinessCheck`, `RequirementClarificationSession` schemas |
| `studio/llm/claude_models.py` | Modify | Add `RequirementClarifierPayload` class |
| `studio/llm/claude_roles.py` | Modify | Register payload in `_ROLE_PAYLOAD_MODELS`, `_ROLE_PROMPTS`, `_ROLE_OUTPUT_FORMATS` |
| `studio/agents/profiles/requirement_clarifier.yaml` | Create | Agent profile for requirement clarifier |
| `.claude/agents/requirement_clarifier/CLAUDE.md` | Create | Claude context directory |
| `studio/storage/workspace.py` | Modify | Add `clarifications` repository + ensure_layout |
| `studio/api/routes/clarifications.py` | Create | POST start, POST message, POST kickoff endpoints |
| `studio/api/main.py` | Modify | Register clarifications router |
| `web/src/lib/api.ts` | Modify | Add `clarificationsApi` methods |
| `web/src/components/common/RequirementClarificationDialog.tsx` | Create | Chat + context preview dialog |
| `web/src/components/board/RequirementCard.tsx` | Modify | Add "Clarify" button for draft requirements |
| `tests/test_clarification_schemas.py` | Create | Schema validation tests |
| `tests/test_clarification_routes.py` | Create | API endpoint tests |

---

### Task 1: Clarification Session Schema

**Files:**
- Create: `studio/schemas/clarification.py`
- Test: `tests/test_clarification_schemas.py`

- [ ] **Step 1: Write schema tests**

```python
# tests/test_clarification_schemas.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.clarification import (
    ClarificationMessage,
    MeetingContextDraft,
    ReadinessCheck,
    RequirementClarificationSession,
)


def test_clarification_message_requires_role_and_content():
    msg = ClarificationMessage(role="user", content="I want combat.")
    assert msg.role == "user"
    assert msg.created_at is not None


def test_clarification_message_rejects_empty_role():
    with pytest.raises(ValidationError):
        ClarificationMessage(role="", content="hello")


def test_clarification_message_rejects_empty_content():
    with pytest.raises(ValidationError):
        ClarificationMessage(role="user", content="")


def test_meeting_context_draft_defaults():
    ctx = MeetingContextDraft(summary="A combat system")
    assert ctx.summary == "A combat system"
    assert ctx.goals == []
    assert ctx.constraints == []
    assert ctx.open_questions == []
    assert ctx.acceptance_criteria == []
    assert ctx.risks == []
    assert ctx.references == []
    assert ctx.validated_attendees == []


def test_meeting_context_draft_rejects_unknown_attendees():
    with pytest.raises(ValidationError):
        MeetingContextDraft(
            summary="test",
            validated_attendees=["design", "producer"],
        )


def test_readiness_check_requires_ready_and_missing_fields():
    r = ReadinessCheck(ready=False, missing_fields=["acceptance_criteria"])
    assert r.ready is False
    assert r.missing_fields == ["acceptance_criteria"]
    assert r.notes == []


def test_session_basic():
    s = RequirementClarificationSession(
        id="clar_req_001",
        requirement_id="req_001",
        status="collecting",
    )
    assert s.status == "collecting"
    assert s.messages == []
    assert s.meeting_context is None
    assert s.project_id is None
    assert s.created_at is not None


def test_session_status_values():
    for status in ("collecting", "ready", "kickoff_started", "completed", "failed"):
        s = RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status=status,
        )
        assert s.status == status


def test_session_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status="unknown",
        )


def test_session_rejects_extra_fields():
    with pytest.raises(ValidationError):
        RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status="collecting",
            extra="oops",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/test_clarification_schemas.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Write the schema**

```python
# studio/schemas/clarification.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr

ClarificationStatus = Literal["collecting", "ready", "kickoff_started", "completed", "failed"]

_SUPPORTED_ATTENDEES = {"design", "art", "dev", "qa"}


class ClarificationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: StrippedNonEmptyStr
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class MeetingContextDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: StrippedNonEmptyStr = "pending"
    goals: list[StrippedNonEmptyStr] = Field(default_factory=list)
    constraints: list[StrippedNonEmptyStr] = Field(default_factory=list)
    open_questions: list[StrippedNonEmptyStr] = Field(default_factory=list)
    acceptance_criteria: list[StrippedNonEmptyStr] = Field(default_factory=list)
    risks: list[StrippedNonEmptyStr] = Field(default_factory=list)
    references: list[StrippedNonEmptyStr] = Field(default_factory=list)
    validated_attendees: list[Literal["design", "art", "dev", "qa"]] = Field(default_factory=list)


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RequirementClarificationSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    status: ClarificationStatus = "collecting"
    messages: list[ClarificationMessage] = Field(default_factory=list)
    meeting_context: MeetingContextDraft | None = None
    readiness: ReadinessCheck | None = None
    project_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/test_clarification_schemas.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/ --tb=short`
Expected: 360 existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add studio/schemas/clarification.py tests/test_clarification_schemas.py
git commit -m "feat: add RequirementClarificationSession schema"
```

---

### Task 2: Requirement Clarifier Agent Profile and Payload

**Files:**
- Create: `studio/agents/profiles/requirement_clarifier.yaml`
- Create: `.claude/agents/requirement_clarifier/CLAUDE.md`
- Modify: `studio/llm/claude_models.py`
- Modify: `studio/llm/claude_roles.py`
- Modify: `tests/test_claude_roles.py`

- [ ] **Step 1: Create agent profile**

```yaml
# studio/agents/profiles/requirement_clarifier.yaml
name: requirement_clarifier
enabled: true
system_prompt: You clarify game feature requirements by asking focused follow-up questions. Return structured JSON with your reply and a meeting context draft. One question at a time. Never invent user decisions.
claude_project_root: .claude/agents/requirement_clarifier
model: sonnet
fallback_policy: strict
```

Create directory and context file:

```bash
mkdir -p .claude/agents/requirement_clarifier
```

```markdown
<!-- .claude/agents/requirement_clarifier/CLAUDE.md -->
This directory belongs only to the requirement clarifier agent.
```

- [ ] **Step 2: Add `RequirementClarifierPayload` to `studio/llm/claude_models.py`**

Read the file first to find the right insertion point (after existing payload classes). Add:

```python
class RequirementClarifierPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    meeting_context: dict[str, object]
    readiness: dict[str, object]
```

- [ ] **Step 3: Register in `studio/llm/claude_roles.py`**

Read the file first. Then:

1. Add to `_ROLE_PAYLOAD_MODELS`:
```python
"requirement_clarifier": RequirementClarifierPayload,
```

2. Add to `_ROLE_PROMPTS`:
```python
"requirement_clarifier": (
    "You are a requirement clarification agent for game development.\n"
    "Analyze the user's description and conversation history.\n"
    "Return only JSON with:\n"
    "- reply: one concise follow-up question or confirmation\n"
    "- meeting_context: object with summary, goals, constraints, open_questions, "
    "acceptance_criteria, risks, references, validated_attendees (subset of: design, art, dev, qa)\n"
    "- readiness: object with ready (bool), missing_fields (list), notes (list)\n"
),
```

3. Add to `_ROLE_OUTPUT_FORMATS`:
```python
"requirement_clarifier": {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "meeting_context": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "goals": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "open_questions": {"type": "array", "items": {"type": "string"}},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "references": {"type": "array", "items": {"type": "string"}},
                "validated_attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary"],
        },
        "readiness": {
            "type": "object",
            "properties": {
                "ready": {"type": "boolean"},
                "missing_fields": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["ready", "missing_fields"],
        },
    },
    "required": ["reply", "meeting_context", "readiness"],
    "additionalProperties": False,
},
```

4. Update `parse_role_payload` return type union and isinstance check to include `RequirementClarifierPayload`.

- [ ] **Step 4: Add role registry test to `tests/test_claude_roles.py`**

```python
def test_supported_role_registry_includes_requirement_clarifier() -> None:
    assert "requirement_clarifier" in claude_roles_module._ACTIVE_ROLE_NAMES
    assert "requirement_clarifier" in claude_roles_module._ROLE_PAYLOAD_MODELS
    assert "requirement_clarifier" in claude_roles_module._ROLE_OUTPUT_FORMATS
```

- [ ] **Step 5: Update agent profiles test**

Read `tests/test_agent_profiles.py` to find the `managed_agents` tuple and add `"requirement_clarifier"`.

- [ ] **Step 6: Run tests**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/test_claude_roles.py tests/test_agent_profiles.py -v`
Expected: PASS

- [ ] **Step 7: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/ --tb=short`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add studio/agents/profiles/requirement_clarifier.yaml .claude/agents/requirement_clarifier/CLAUDE.md studio/llm/claude_models.py studio/llm/claude_roles.py tests/test_claude_roles.py tests/test_agent_profiles.py
git commit -m "feat: add requirement clarifier agent profile and payload"
```

---

### Task 3: Workspace Integration

**Files:**
- Modify: `studio/storage/workspace.py`

- [ ] **Step 1: Read `studio/storage/workspace.py` and add clarifications repository**

Add import:
```python
from studio.schemas.clarification import RequirementClarificationSession
```

Add to `__init__`:
```python
        self.clarifications = JsonRepository(root / "requirement_clarifications", RequirementClarificationSession)
```

Add `self.clarifications.root` to `ensure_layout` tuple.

- [ ] **Step 2: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/ --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add studio/storage/workspace.py
git commit -m "feat: add clarifications repository to StudioWorkspace"
```

---

### Task 4: Clarification API Routes

**Files:**
- Create: `studio/api/routes/clarifications.py`
- Modify: `studio/api/main.py`
- Test: `tests/test_clarification_routes.py`

This is the core backend task. Three endpoints: start/resume session, send message, start kickoff.

- [ ] **Step 1: Write API route tests**

```python
# tests/test_clarification_routes.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def client(tmp_path: Path):
    from studio.api.main import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def workspace(tmp_path: Path) -> str:
    ws = tmp_path / ".studio-data"
    workspace = StudioWorkspace(ws)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat system"))
    return str(tmp_path)


def test_start_creates_session(client, workspace):
    response = client.post(
        f"/api/requirements/req_001/clarification?workspace={workspace}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["requirement_id"] == "req_001"
    assert data["session"]["status"] == "collecting"


def test_start_returns_existing_session(client, workspace):
    r1 = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    r2 = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    assert r1.json()["session"]["id"] == r2.json()["session"]["id"]


def test_start_fails_for_missing_requirement(client, workspace):
    response = client.post(
        f"/api/requirements/req_999/clarification?workspace={workspace}"
    )
    assert response.status_code == 404


def test_send_message_appends_to_session(client, workspace):
    start = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    with patch("studio.api.routes.clarifications.ClaudeRoleAdapter") as MockAdapter:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = type(
            "Payload", (), {
                "reply": "Should combat be real-time or turn-based?",
                "meeting_context": {
                    "summary": "Combat system",
                    "goals": [],
                    "constraints": [],
                    "open_questions": ["Real-time or turn-based?"],
                    "acceptance_criteria": [],
                    "risks": [],
                    "references": [],
                    "validated_attendees": ["design", "dev"],
                },
                "readiness": {"ready": False, "missing_fields": ["acceptance_criteria"], "notes": []},
            }
        )()
        MockAdapter.return_value = mock_instance

        response = client.post(
            f"/api/requirements/req_001/clarification/messages?workspace={workspace}",
            json={"message": "I want a combat system.", "session_id": session_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"] == "Should combat be real-time or turn-based?"
    session = data["session"]
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_send_message_rejects_empty_message(client, workspace):
    start = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    response = client.post(
        f"/api/requirements/req_001/clarification/messages?workspace={workspace}",
        json={"message": "", "session_id": session_id},
    )
    assert response.status_code == 422


def test_send_message_rejects_missing_session_id(client, workspace):
    response = client.post(
        f"/api/requirements/req_001/clarification/messages?workspace={workspace}",
        json={"message": "hello"},
    )
    assert response.status_code == 422


def test_kickoff_rejects_unready_session(client, workspace):
    start = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    response = client.post(
        f"/api/requirements/req_001/clarification/kickoff?workspace={workspace}",
        json={"session_id": session_id},
    )
    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


def test_kickoff_creates_project_and_runs_meeting(client, workspace):
    start = client.post(f"/api/requirements/req_001/clarification?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    # Manually set session to ready with valid context
    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    session = ws.clarifications.get(session_id)
    from studio.schemas.clarification import MeetingContextDraft, ReadinessCheck
    session = session.model_copy(update={
        "meeting_context": MeetingContextDraft(
            summary="Combat system",
            goals=["Define MVP combat loop"],
            acceptance_criteria=["3v3 battle completes"],
            risks=["Scope growth"],
            validated_attendees=["design", "dev"],
        ),
        "readiness": ReadinessCheck(ready=True, missing_fields=[]),
        "status": "ready",
    })
    ws.clarifications.save(session)

    with patch("studio.api.routes.clarifications.SessionRegistry") as MockRegistry, \
         patch("studio.api.routes.clarifications.build_meeting_graph") as MockGraph:
        mock_reg = MagicMock()
        mock_reg.create_all.return_value = []
        MockRegistry.return_value = mock_reg

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "moderator_minutes",
            "minutes": {"id": "meeting_001", "requirement_id": "req_001"},
        }
        MockGraph.return_value = mock_graph

        response = client.post(
            f"/api/requirements/req_001/clarification/kickoff?workspace={workspace}",
            json={"session_id": session_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"].startswith("proj_")
    assert data["requirement_id"] == "req_001"
    assert data["status"] == "kickoff_complete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/test_clarification_routes.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Create `studio/api/routes/clarifications.py`**

Read `studio/api/routes/requirements.py` for the exact pattern, then create:

```python
# studio/api/routes/clarifications.py
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter
from studio.runtime.graph import build_meeting_graph
from studio.schemas.clarification import (
    ClarificationMessage,
    MeetingContextDraft,
    ReadinessCheck,
    RequirementClarificationSession,
)
from studio.storage.session_registry import SessionRegistry
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/clarifications", tags=["clarifications"])

_SUPPORTED_ATTENDEES = {"design", "art", "dev", "qa"}
_MANAGED_AGENTS = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
_REQUIRED_FIELDS = ["summary", "goals", "acceptance_criteria", "risks"]


class SendMessageRequest(BaseModel):
    message: str
    session_id: str


class KickoffRequest(BaseModel):
    session_id: str


def _get_workspace(workspace: str) -> StudioWorkspace:
    workspace_path = Path(workspace) / ".studio-data"
    return StudioWorkspace(workspace_path)


def _validate_readiness(context: MeetingContextDraft) -> ReadinessCheck:
    missing: list[str] = []
    notes: list[str] = []

    if not context.summary or context.summary == "pending":
        missing.append("summary")
    if not context.goals:
        missing.append("goals")
    if not context.acceptance_criteria:
        missing.append("acceptance_criteria")
    if not context.risks:
        notes.append("No risks identified — consider whether scope or complexity risks apply.")

    return ReadinessCheck(
        ready=len(missing) == 0,
        missing_fields=missing,
        notes=notes,
    )


def _find_session_for_requirement(
    store: StudioWorkspace, requirement_id: str
) -> RequirementClarificationSession | None:
    for session in store.clarifications.list_all():
        if session.requirement_id == requirement_id and session.status in ("collecting", "ready", "failed"):
            return session
    return None


@router.post("/requirements/{req_id}/session")
async def start_or_get_session(workspace: str, req_id: str) -> dict:
    store = _get_workspace(workspace)
    store.ensure_layout()

    try:
        store.requirements.get(req_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Requirement not found")

    existing = _find_session_for_requirement(store, req_id)
    if existing is not None:
        return {"session": json.loads(existing.model_dump_json())}

    session = RequirementClarificationSession(
        id=f"clar_{req_id}",
        requirement_id=req_id,
        status="collecting",
    )
    saved = store.clarifications.save(session)
    return {"session": json.loads(saved.model_dump_json())}


@router.post("/requirements/{req_id}/messages")
async def send_message(workspace: str, req_id: str, request: SendMessageRequest) -> dict:
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message must not be empty")

    store = _get_workspace(workspace)

    try:
        session = store.clarifications.get(request.session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("collecting", "ready", "failed"):
        raise HTTPException(status_code=400, detail=f"Session is {session.status}, cannot accept messages")

    # Append user message
    user_msg = ClarificationMessage(role="user", content=request.message.strip())
    session.messages.append(user_msg)

    # Call clarification agent
    try:
        profile = AgentProfileLoader().load("requirement_clarifier")
        adapter = ClaudeRoleAdapter(profile=profile)
        conversation_history = [
            {"role": m.role, "content": m.content} for m in session.messages
        ]
        payload = adapter.generate(
            "requirement_clarifier",
            {
                "requirement_id": req_id,
                "conversation": conversation_history,
                "current_context": session.meeting_context.model_dump() if session.meeting_context else {},
            },
        )
    except Exception as exc:
        session = session.model_copy(update={"status": "failed", "updated_at": datetime.now(UTC).isoformat()})
        store.clarifications.save(session)
        raise HTTPException(status_code=502, detail=f"Clarification agent failed: {exc}")

    # Parse structured output
    reply_text = str(payload.reply)
    assistant_msg = ClarificationMessage(role="assistant", content=reply_text)
    session.messages.append(assistant_msg)

    raw_context = payload.meeting_context if isinstance(payload.meeting_context, dict) else {}
    draft = MeetingContextDraft(
        summary=str(raw_context.get("summary", session.meeting_context.summary if session.meeting_context else "pending")),
        goals=[str(g) for g in raw_context.get("goals", [])],
        constraints=[str(c) for c in raw_context.get("constraints", [])],
        open_questions=[str(q) for q in raw_context.get("open_questions", [])],
        acceptance_criteria=[str(a) for a in raw_context.get("acceptance_criteria", [])],
        risks=[str(r) for r in raw_context.get("risks", [])],
        references=[str(ref) for ref in raw_context.get("references", [])],
        validated_attendees=[a for a in raw_context.get("validated_attendees", []) if a in _SUPPORTED_ATTENDEES],
    )

    readiness = _validate_readiness(draft)
    new_status = "ready" if readiness.ready else "collecting"

    session = session.model_copy(update={
        "meeting_context": draft,
        "readiness": readiness,
        "status": new_status,
        "updated_at": datetime.now(UTC).isoformat(),
    })
    store.clarifications.save(session)

    return {
        "session": json.loads(session.model_dump_json()),
        "assistant_message": reply_text,
    }


@router.post("/requirements/{req_id}/kickoff")
async def start_kickoff(workspace: str, req_id: str, request: KickoffRequest) -> dict:
    store = _get_workspace(workspace)

    try:
        session = store.clarifications.get(request.session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    if session.meeting_context is None or not session.readiness or not session.readiness.ready:
        missing = session.readiness.missing_fields if session.readiness else ["unknown"]
        raise HTTPException(status_code=400, detail=f"Session not ready for kickoff. Missing: {', '.join(missing)}")

    # Validate attendees
    for attendee in session.meeting_context.validated_attendees:
        if attendee not in _SUPPORTED_ATTENDEES:
            raise HTTPException(status_code=400, detail=f"Unsupported attendee: {attendee}")

    session = session.model_copy(update={"status": "kickoff_started", "updated_at": datetime.now(UTC).isoformat()})
    store.clarifications.save(session)

    # Create project-agent sessions
    ws_root = Path(workspace) / ".studio-data"
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    registry = SessionRegistry(ws_root)
    registry.create_all(project_id, req_id, _MANAGED_AGENTS)

    # Run meeting graph
    project_root = str(Path(workspace).parent.parent) if ws_root.name == ".studio-data" else str(workspace)
    graph = build_meeting_graph()
    result = graph.invoke({
        "workspace_root": str(ws_root),
        "project_root": project_root,
        "requirement_id": req_id,
        "user_intent": f"Kickoff meeting for clarified requirement: {session.meeting_context.summary}",
        "project_id": project_id,
        "meeting_context": session.meeting_context.model_dump(),
    })

    meeting_id = result.get("minutes", {}).get("id", "")

    session = session.model_copy(update={
        "status": "completed",
        "project_id": project_id,
        "updated_at": datetime.now(UTC).isoformat(),
    })
    store.clarifications.save(session)

    return {
        "project_id": project_id,
        "requirement_id": req_id,
        "meeting_id": meeting_id,
        "status": "kickoff_complete",
    }
```

- [ ] **Step 4: Register in `studio/api/main.py`**

Read `studio/api/main.py`, add `clarifications` to the imports and:
```python
app.include_router(clarifications.router, prefix="/api")
```

- [ ] **Step 5: Run tests**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/test_clarification_routes.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full suite**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog && python -m pytest tests/ --tb=short`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add studio/api/routes/clarifications.py studio/api/main.py tests/test_clarification_routes.py
git commit -m "feat: add clarification session API with message and kickoff endpoints"
```

---

### Task 5: Frontend API Client

**Files:**
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Read `web/src/lib/api.ts` to understand the pattern**

- [ ] **Step 2: Add clarification API types and methods**

Add these interfaces and methods to the file, following existing patterns:

```typescript
// Interfaces
export interface ClarificationMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface MeetingContextDraft {
  summary: string
  goals: string[]
  constraints: string[]
  open_questions: string[]
  acceptance_criteria: string[]
  risks: string[]
  references: string[]
  validated_attendees: string[]
}

export interface ReadinessCheck {
  ready: boolean
  missing_fields: string[]
  notes: string[]
}

export interface ClarificationSession {
  id: string
  requirement_id: string
  status: string
  messages: ClarificationMessage[]
  meeting_context: MeetingContextDraft | null
  readiness: ReadinessCheck | null
  project_id: string | null
  created_at: string
  updated_at: string
}

// API methods
export const clarificationsApi = {
  start: (workspace: string, requirementId: string): Promise<{ session: ClarificationSession }> =>
    apiRequest(`/clarifications/requirements/${requirementId}/session`, 'post', {
      params: { workspace },
    }),

  sendMessage: (
    workspace: string,
    requirementId: string,
    sessionId: string,
    message: string,
  ): Promise<{ session: ClarificationSession; assistant_message: string }> =>
    apiRequest(`/clarifications/requirements/${requirementId}/messages`, 'post', {
      params: { workspace },
      body: JSON.stringify({ message, session_id: sessionId }),
      headers: { 'Content-Type': 'application/json' },
    }),

  kickoff: (
    workspace: string,
    requirementId: string,
    sessionId: string,
  ): Promise<{ project_id: string; requirement_id: string; meeting_id: string; status: string }> =>
    apiRequest(`/clarifications/requirements/${requirementId}/kickoff`, 'post', {
      params: { workspace },
      body: JSON.stringify({ session_id: sessionId }),
      headers: { 'Content-Type': 'application/json' },
    }),
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog/web && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (or only pre-existing errors)

- [ ] **Step 4: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add web/src/lib/api.ts
git commit -m "feat: add clarification API client methods"
```

---

### Task 6: Frontend Clarification Dialog

**Files:**
- Create: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] **Step 1: Read existing dialog components for patterns**

Read `web/src/components/common/CreateRequirementDialog.tsx` and `web/src/components/ui/dialog.tsx` for the exact component patterns.

- [ ] **Step 2: Create the dialog component**

```tsx
import { useState, useRef, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useMutation, useQuery } from '@tanstack/react-query'
import { clarificationsApi, type ClarificationSession, type MeetingContextDraft } from '@/lib/api'

interface RequirementClarificationDialogProps {
  workspace: string
  requirementId: string
  requirementTitle: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const REQUIRED_FIELDS: { key: keyof MeetingContextDraft; label: string }[] = [
  { key: 'summary', label: 'Summary' },
  { key: 'goals', label: 'Goals' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'risks', label: 'Risks' },
]

function isFieldComplete(ctx: MeetingContextDraft | null, key: keyof MeetingContextDraft): boolean {
  if (!ctx) return false
  const value = ctx[key]
  if (Array.isArray(value)) return value.length > 0
  return typeof value === 'string' && value.length > 0 && value !== 'pending'
}

export function RequirementClarificationDialog({
  workspace,
  requirementId,
  requirementTitle,
  open,
  onOpenChange,
}: RequirementClarificationDialogProps) {
  const [message, setMessage] = useState('')
  const [session, setSession] = useState<ClarificationSession | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const startMutation = useMutation({
    mutationFn: () => clarificationsApi.start(workspace, requirementId),
    onSuccess: (data) => setSession(data.session),
  })

  const sendMutation = useMutation({
    mutationFn: (msg: string) =>
      clarificationsApi.sendMessage(workspace, requirementId, session!.id, msg),
    onSuccess: (data) => {
      setSession(data.session)
      setMessage('')
    },
  })

  const kickoffMutation = useMutation({
    mutationFn: () =>
      clarificationsApi.kickoff(workspace, requirementId, session!.id),
    onSuccess: () => {
      onOpenChange(false)
    },
  })

  useEffect(() => {
    if (open && !session) {
      startMutation.mutate()
    }
  }, [open])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages?.length])

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim() || sendMutation.isPending) return
    sendMutation.mutate(message.trim())
  }

  const canKickoff = session?.readiness?.ready && !kickoffMutation.isPending
  const context = session?.meeting_context ?? null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Clarify: {requirementTitle}
            {session && (
              <Badge variant={session.status === 'ready' ? 'default' : 'secondary'}>
                {session.status}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex gap-4 min-h-[400px]">
          {/* Chat column */}
          <div className="flex-1 flex flex-col">
            <div className="flex-1 overflow-y-auto space-y-3 mb-3 pr-2">
              {session?.messages.map((msg, i) => (
                <div
                  key={i}
                  className={`p-2 rounded text-sm ${
                    msg.role === 'user'
                      ? 'bg-blue-50 ml-8'
                      : 'bg-gray-50 mr-8'
                  }`}
                >
                  <span className="text-xs text-muted-foreground block mb-1">
                    {msg.role === 'user' ? 'You' : 'Agent'}
                  </span>
                  {msg.content}
                </div>
              ))}
              {sendMutation.isPending && (
                <div className="bg-gray-50 mr-8 p-2 rounded text-sm text-muted-foreground">
                  Thinking...
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="flex gap-2">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe the feature..."
                disabled={sendMutation.isPending}
                className="flex-1"
              />
              <Button type="submit" disabled={!message.trim() || sendMutation.isPending}>
                Send
              </Button>
            </form>
          </div>

          {/* Context preview column */}
          <div className="w-72 border-l pl-4 space-y-3 overflow-y-auto">
            <h4 className="font-medium text-sm">Context Preview</h4>

            {REQUIRED_FIELDS.map(({ key, label }) => (
              <div key={key}>
                <div className="flex items-center gap-1 text-sm">
                  <span className={isFieldComplete(context, key) ? 'text-green-600' : 'text-amber-500'}>
                    {isFieldComplete(context, key) ? '\u2713' : '\u25CB'}
                  </span>
                  <span className="font-medium">{label}</span>
                </div>
                {context && (
                  <ul className="text-xs text-muted-foreground ml-4 mt-1 space-y-0.5">
                    {(Array.isArray(context[key]) ? context[key] : [context[key]]).map(
                      (item, i) => typeof item === 'string' && item !== 'pending' && (
                        <li key={i}>{item}</li>
                      ),
                    )}
                  </ul>
                )}
              </div>
            ))}

            {context?.validated_attendees && context.validated_attendees.length > 0 && (
              <div>
                <span className="font-medium text-sm">Attendees</span>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {context.validated_attendees.map((a) => (
                    <Badge key={a} variant="outline" className="text-xs">{a}</Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-4 border-t">
              <Button
                className="w-full"
                disabled={!canKickoff}
                onClick={() => kickoffMutation.mutate()}
              >
                {kickoffMutation.isPending ? 'Starting...' : 'Start Kickoff Meeting'}
              </Button>
              {session?.readiness && !session.readiness.ready && (
                <p className="text-xs text-amber-600 mt-1">
                  Missing: {session.readiness.missing_fields.join(', ')}
                </p>
              )}
              {kickoffMutation.isError && (
                <p className="text-xs text-red-600 mt-1">
                  {String(kickoffMutation.error)}
                </p>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add web/src/components/common/RequirementClarificationDialog.tsx
git commit -m "feat: add RequirementClarificationDialog component"
```

---

### Task 7: Frontend Card Integration

**Files:**
- Modify: `web/src/components/board/RequirementCard.tsx`
- Modify: `web/src/pages/RequirementsBoard.tsx`

- [ ] **Step 1: Add "Clarify" button to RequirementCard**

Read `web/src/components/board/RequirementCard.tsx`. Add a state for dialog open and import the dialog. The "Clarify" button should only appear for draft/designing requirements:

Add to the component, after the existing `View Design` link:

```tsx
{['draft', 'designing'].includes(statusValue) && (
  <button
    className="text-xs text-blue-600 hover:underline mt-1 block"
    onClick={(e) => {
      e.stopPropagation()
      // Dialog open handled by parent via prop
      if (onClarify) onClarify()
    }}
  >
    Clarify
  </button>
)}
```

Add `onClarify?: () => void` to `RequirementCardProps`.

- [ ] **Step 2: Wire dialog in RequirementsBoard**

Read `web/src/pages/RequirementsBoard.tsx`. Add state for which requirement is being clarified and render the dialog:

```tsx
import { useState } from 'react'
import { RequirementClarificationDialog } from '@/components/common/RequirementClarificationDialog'

// Inside the component:
const [clarifyReq, setClarifyReq] = useState<{ id: string; title: string } | null>(null)

// Pass onClarify to RequirementCard:
<RequirementCard
  // ... existing props
  onClarify={() => setClarifyReq({ id: req.id, title: req.title })}
/>

// After the board, render dialog:
{clarifyReq && (
  <RequirementClarificationDialog
    workspace={workspace}
    requirementId={clarifyReq.id}
    requirementTitle={clarifyReq.title}
    open={!!clarifyReq}
    onOpenChange={(open) => { if (!open) setClarifyReq(null) }}
  />
)}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
cd F:/projs/Game_Studio/.worktrees/requirement-clarification-dialog
git add web/src/components/board/RequirementCard.tsx web/src/pages/RequirementsBoard.tsx
git commit -m "feat: add Clarify button and dialog integration on requirement cards"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Data model (RequirementClarificationSession) → Task 1
  - Agent contract (payload + profile) → Task 2
  - Workspace storage → Task 3
  - API routes (start, message, kickoff) → Task 4
  - Frontend API client → Task 5
  - Frontend dialog → Task 6
  - Frontend card integration → Task 7
  - Readiness validation → Task 4 (server-side)
  - Attendee validation → Task 4
  - Error handling (no fake fallback) → Task 4
  - WebSocket broadcast → not explicitly tasked (can be added later, not blocking)

- [x] **Placeholder scan:** No TBD/TODO/placeholder steps.

- [x] **Type consistency:** `RequirementClarificationSession` fields match across schema, API routes, and frontend interfaces. `validated_attendees` uses same set (`design`, `art`, `dev`, `qa`) throughout. Session ID format `clar_{req_id}` consistent.
