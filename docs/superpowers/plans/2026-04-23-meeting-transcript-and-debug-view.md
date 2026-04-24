# Meeting Transcript And Debug View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist per-agent meeting discussion events and expose them in a chat-style transcript view with optional prompt/reply expansion.

**Architecture:** Capture prompt/reply debug records from meeting agents inside the meeting graph, normalize them into transcript events, persist them as a dedicated meeting transcript artifact, expose them through a transcript API, and render them in a chat-style UI with expandable debug details.

**Tech Stack:** FastAPI, Pydantic, React, TypeScript, TanStack Query, pytest

---

## File Structure

### Backend

- Create: `studio/schemas/meeting_transcript.py`
- Modify: `studio/storage/workspace.py`
- Modify: `studio/runtime/graph.py`
- Modify: `studio/api/routes/meetings.py`

### Frontend

- Modify: `web/src/lib/api.ts`
- Create: `web/src/components/common/MeetingTranscriptDialog.tsx`
- Modify: kickoff result / meeting result entry component

### Tests

- Create or modify backend transcript tests near meeting route / graph tests
- Modify: `tests/test_clarification_routes.py` only if kickoff result links are extended

---

### Task 1: Add Transcript Schema And Storage

**Files:**
- Create: `studio/schemas/meeting_transcript.py`
- Modify: `studio/storage/workspace.py`
- Test: add a focused schema/storage test file if no existing location fits

- [ ] **Step 1: Write the failing schema/storage test**

Add a test covering:

- transcript model validation
- repository persistence under `.studio-data/meeting_transcripts`

Suggested test shape:

```python
def test_workspace_persists_meeting_transcript(tmp_path: Path) -> None:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    transcript = MeetingTranscript(
        id="transcript_meeting_001",
        meeting_id="meeting_001",
        requirement_id="req_001",
        project_id="proj_001",
        events=[
            MeetingTranscriptEvent(
                id="evt_001",
                meeting_id="meeting_001",
                sequence=1,
                phase="agent_opinion",
                speaker="design",
                event_type="llm_exchange",
                summary="Design proposed a browser MVP.",
                prompt="prompt text",
                raw_reply="reply text",
                parsed_payload={"summary": "Design proposed a browser MVP."},
            )
        ],
    )

    ws.meeting_transcripts.save(transcript)
    loaded = ws.meeting_transcripts.get("transcript_meeting_001")

    assert loaded.meeting_id == "meeting_001"
    assert loaded.events[0].speaker == "design"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_storage.py -q
```

Expected:

- FAIL because schema/repository do not exist yet

- [ ] **Step 3: Implement minimal schema**

Create `studio/schemas/meeting_transcript.py` with:

- `MeetingTranscriptEvent`
- `MeetingTranscript`

Suggested fields:

```python
class MeetingTranscriptEvent(BaseModel):
    id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    sequence: int
    phase: StrippedNonEmptyStr
    speaker: StrippedNonEmptyStr
    event_type: Literal["llm_exchange"] = "llm_exchange"
    summary: str = ""
    prompt: str | None = None
    raw_reply: str | None = None
    parsed_payload: dict[str, object] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

```python
class MeetingTranscript(BaseModel):
    id: StrippedNonEmptyStr
    meeting_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    events: list[MeetingTranscriptEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

- [ ] **Step 4: Register transcript repository in workspace**

Update `studio/storage/workspace.py`:

- import `MeetingTranscript`
- add `self.meeting_transcripts = JsonRepository(root / "meeting_transcripts", MeetingTranscript)`
- include its root in `ensure_layout()`

- [ ] **Step 5: Run focused tests and verify green**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_storage.py -q
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```powershell
git add studio/schemas/meeting_transcript.py studio/storage/workspace.py tests/test_meeting_transcript_storage.py
git commit -m "Add meeting transcript schema and storage"
```

---

### Task 2: Capture Transcript Events In Meeting Graph

**Files:**
- Modify: `studio/runtime/graph.py`
- Possibly inspect: `studio/agents/moderator.py`, `studio/agents/design.py`, `studio/agents/dev.py`, `studio/agents/qa.py`
- Test: new or existing meeting graph tests

- [ ] **Step 1: Write a failing graph-level test**

Add a focused test that simulates a meeting run and asserts transcript events are persisted.

Minimum assertions:

- transcript exists after meeting completion
- transcript contains at least one moderator event and one agent event

Suggested test shape:

```python
def test_meeting_graph_persists_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # arrange workspace and fake agent outputs
    # invoke build_meeting_graph().invoke(...)
    transcript = StudioWorkspace(tmp_path / ".studio-data").meeting_transcripts.list_all()[0]
    assert transcript.meeting_id.startswith("meeting_")
    assert any(event.speaker == "moderator" for event in transcript.events)
    assert any(event.speaker == "design" for event in transcript.events)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_graph.py -q
```

Expected:

- FAIL because no transcript is persisted yet

- [ ] **Step 3: Add transcript collection helpers in `graph.py`**

Implement small helpers:

- normalize debug records into `MeetingTranscriptEvent`
- append events into graph state, for example under `_transcript_events`

Suggested helper shape:

```python
def _append_transcript_event(
    state: dict[str, object],
    *,
    meeting_id: str | None,
    phase: str,
    speaker: str,
    record: dict[str, object] | None,
) -> None:
    ...
```

Use the agent `consume_llm_log_entry()` hooks immediately after each successful model call.

- [ ] **Step 4: Capture records in each meeting node**

At minimum capture:

- moderator prepare
- each agent opinion
- moderator summarize
- moderator discussion
- moderator minutes

For each event:

- `phase`: graph node name or normalized phase
- `speaker`: `moderator` or agent role
- `summary`: derived from parsed payload / telemetry
- `prompt`: `record.get("prompt")`
- `raw_reply`: serialized `record.get("reply")`
- `parsed_payload`: node telemetry payload when available

- [ ] **Step 5: Persist transcript at meeting completion**

In `moderator_minutes_node`, after meeting minutes are saved, also save:

```python
transcript = MeetingTranscript(
    id=f"transcript_{minutes.id}",
    meeting_id=minutes.id,
    requirement_id=requirement_id,
    project_id=str(state.get("project_id", "")),
    events=events,
)
workspace.meeting_transcripts.save(transcript)
```

If transcript persistence fails:

- catch the exception
- do not fail meeting completion

- [ ] **Step 6: Run focused graph tests**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_graph.py -q
```

Expected:

- PASS

- [ ] **Step 7: Run broader related tests**

Run:

```powershell
uv run pytest tests/test_clarification_routes.py tests/test_delivery_api.py -q
```

Expected:

- PASS

- [ ] **Step 8: Commit**

```powershell
git add studio/runtime/graph.py tests/test_meeting_transcript_graph.py
git commit -m "Persist transcript events for meetings"
```

---

### Task 3: Add Meeting Transcript API

**Files:**
- Modify: `studio/api/routes/meetings.py`
- Test: new meeting transcript route test

- [ ] **Step 1: Write a failing route test**

Add a test for:

- `GET /api/meetings/{meeting_id}/transcript`

Suggested shape:

```python
def test_get_meeting_transcript_returns_transcript(client: TestClient, workspace: Path) -> None:
    ws = StudioWorkspace(workspace / ".studio-data")
    ws.ensure_layout()
    ws.meeting_transcripts.save(...)

    resp = client.get(
        "/api/meetings/meeting_001/transcript",
        params={"workspace": str(workspace)},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == "meeting_001"
    assert len(data["events"]) == 1
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_api.py -q
```

Expected:

- FAIL because endpoint does not exist yet

- [ ] **Step 3: Implement transcript endpoint**

Extend `studio/api/routes/meetings.py` with:

```python
@router.get("/{meeting_id}/transcript")
async def get_meeting_transcript(workspace: str, meeting_id: str) -> dict:
    store = _get_workspace(workspace)
    try:
        return store.meeting_transcripts.get(f"transcript_{meeting_id}").model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting transcript not found")
```

- [ ] **Step 4: Run focused route tests**

Run:

```powershell
uv run pytest tests/test_meeting_transcript_api.py -q
```

Expected:

- PASS

- [ ] **Step 5: Run broader API regression**

Run:

```powershell
uv run pytest tests/test_clarification_routes.py tests/test_delivery_api.py tests/test_meeting_transcript_api.py -q
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```powershell
git add studio/api/routes/meetings.py tests/test_meeting_transcript_api.py
git commit -m "Add meeting transcript API"
```

---

### Task 4: Add Transcript Types And API Client In Frontend

**Files:**
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add transcript types**

Define:

```ts
export interface MeetingTranscriptEvent {
  id: string
  meeting_id: string
  sequence: number
  phase: string
  speaker: string
  event_type: 'llm_exchange'
  summary: string
  prompt: string | null
  raw_reply: string | null
  parsed_payload: Record<string, unknown>
  created_at: string
}

export interface MeetingTranscript {
  id: string
  meeting_id: string
  requirement_id: string
  project_id: string
  events: MeetingTranscriptEvent[]
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Add transcript fetch API**

Add:

```ts
meetingsApi: {
  getTranscript: (workspace: string, meetingId: string): Promise<MeetingTranscript> =>
    apiRequest(`/meetings/${meetingId}/transcript`, 'get', {
      params: { workspace },
    }) as Promise<MeetingTranscript>,
}
```

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected:

- PASS or only expected failures from not-yet-created UI imports

- [ ] **Step 4: Commit**

```powershell
git add web/src/lib/api.ts
git commit -m "Add meeting transcript frontend API types"
```

---

### Task 5: Build Chat-Style Transcript Viewer

**Files:**
- Create: `web/src/components/common/MeetingTranscriptDialog.tsx`
- Modify: appropriate meeting-result entry point component

- [ ] **Step 1: Create transcript viewer component**

Build a dialog component that:

- fetches transcript by `meetingId`
- lists events in sequence order
- renders speaker badge and phase label
- shows concise summary first

Suggested structure:

```tsx
export function MeetingTranscriptDialog({ workspace, meetingId, open, onOpenChange }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['meeting-transcript', workspace, meetingId],
    queryFn: () => meetingsApi.getTranscript(workspace, meetingId),
    enabled: open,
  })
  ...
}
```

- [ ] **Step 2: Add per-event expansion**

Each event card should expand to show:

- prompt
- raw reply
- parsed payload

Suggested behavior:

- collapsed by default
- use local `expandedEventIds` state or a simple disclosure pattern

- [ ] **Step 3: Keep default transcript readable**

Render the top-level card like chat:

```tsx
<div className="rounded-lg border bg-white p-4">
  <div className="flex items-center gap-2">
    <Badge>{event.speaker}</Badge>
    <span className="text-xs text-muted-foreground">{event.phase}</span>
  </div>
  <p className="mt-2 text-sm">{event.summary || '(No summary captured)'}</p>
</div>
```

- [ ] **Step 4: Wire entry point**

Add a visible button where meeting results are shown:

- `View Meeting Transcript`

This can first be added to the kickoff result UI or current meeting result UI path.

- [ ] **Step 5: Run frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected:

- PASS

- [ ] **Step 6: Manual verification**

Run:

```powershell
uv run uvicorn studio.api.main:create_app --factory --reload
```

```powershell
npm --prefix web run dev
```

Expected:

- complete a kickoff
- click `View Meeting Transcript`
- see a chat-style transcript
- expand at least one event and confirm prompt/raw reply are visible

- [ ] **Step 7: Commit**

```powershell
git add web/src/components/common/MeetingTranscriptDialog.tsx
git add <meeting result entry component>
git commit -m "Add meeting transcript viewer"
```

---

## Plan Self-Review

### Spec Coverage

- transcript persistence: Task 1 and Task 2
- transcript API: Task 3
- chat-style view: Task 5
- prompt/raw reply debugging: Task 5
- non-blocking meeting completion: Task 2

### Placeholder Scan

- No `TBD` or deferred implementation placeholders remain
- Each task includes exact files and verification commands

### Type Consistency

- `MeetingTranscript` and `MeetingTranscriptEvent` are introduced once and reused consistently
- `meeting_id` is the join key across storage, API, and frontend

---

Plan complete and saved to `docs/superpowers/plans/2026-04-23-meeting-transcript-and-debug-view.md`.

Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
