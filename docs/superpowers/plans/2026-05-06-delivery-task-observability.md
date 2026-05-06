# Delivery Task Observability And Session Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Delivery task event timelines and task-scoped Claude session visibility to the Delivery Board.

**Architecture:** Persist task execution events in workspace storage, record those events from the Delivery runner and retry API, expose task events and task session transcript APIs, then add a Delivery task detail drawer with Overview, Events, Agent Session, and Artifacts tabs.

**Tech Stack:** FastAPI, Pydantic, LangGraph runner code, React, TypeScript, TanStack Query, pytest, Vite

---

## File Structure

Backend:

- Create: `studio/schemas/delivery_events.py`
- Modify: `studio/storage/workspace.py`
- Modify: `studio/storage/delivery_plan_service.py`
- Modify: `studio/runtime/graph.py`
- Modify: `studio/api/routes/delivery.py`
- Test: `tests/test_delivery_events.py`
- Test: `tests/test_delivery_api.py`
- Test: `tests/test_delivery_graph.py`

Frontend:

- Modify: `web/src/lib/api.ts`
- Modify: `web/src/components/board/DeliveryTaskCard.tsx`
- Modify: `web/src/pages/DeliveryBoard.tsx`
- Create: `web/src/components/board/DeliveryTaskDetailDrawer.tsx`

---

### Task 1: Add Delivery Task Event Schema And Storage

**Files:**
- Create: `studio/schemas/delivery_events.py`
- Modify: `studio/storage/workspace.py`
- Test: `tests/test_delivery_events.py`

- [ ] **Step 1: Write the failing event storage test**

Add `tests/test_delivery_events.py`:

```python
from __future__ import annotations

from pathlib import Path

from studio.schemas.delivery_events import DeliveryTaskEvent
from studio.storage.workspace import StudioWorkspace


def test_workspace_persists_delivery_task_events(tmp_path: Path) -> None:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()

    event = DeliveryTaskEvent(
        id="evt_task_001_0001",
        task_id="task_001",
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        agent="dev",
        event_type="task_started",
        message="dev started task Implement game UI.",
        metadata={"attempt_count": 1, "session_id": "sess_dev"},
    )

    ws.delivery_task_events.save(event)
    loaded = ws.delivery_task_events.get("evt_task_001_0001")

    assert loaded.task_id == "task_001"
    assert loaded.event_type == "task_started"
    assert loaded.metadata["session_id"] == "sess_dev"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/test_delivery_events.py -q
```

Expected: FAIL because `studio.schemas.delivery_events` and `delivery_task_events` repository do not exist.

- [ ] **Step 3: Implement event schema**

Create `studio/schemas/delivery_events.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


DeliveryTaskEventType = Literal[
    "task_started",
    "agent_session_attached",
    "agent_invocation_started",
    "agent_invocation_completed",
    "file_changes_detected",
    "task_completed",
    "task_failed",
    "task_retried",
]


class DeliveryTaskEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    task_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    agent: StrippedNonEmptyStr
    event_type: DeliveryTaskEventType
    message: StrippedNonEmptyStr
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
```

- [ ] **Step 4: Register repository in workspace**

In `studio/storage/workspace.py`:

```python
from studio.schemas.delivery_events import DeliveryTaskEvent
```

Add in `StudioWorkspace.__init__`:

```python
self.delivery_task_events = JsonRepository(root / "delivery_task_events", DeliveryTaskEvent)
```

Add `self.delivery_task_events.root` to `ensure_layout()`.

- [ ] **Step 5: Run focused test and verify green**

Run:

```powershell
uv run pytest tests/test_delivery_events.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add studio/schemas/delivery_events.py studio/storage/workspace.py tests/test_delivery_events.py
git commit -m "feat: add delivery task event storage"
```

---

### Task 2: Add Event Recording Service Behavior

**Files:**
- Modify: `studio/storage/delivery_plan_service.py`
- Test: `tests/test_delivery_events.py`

- [ ] **Step 1: Write failing service tests**

Append to `tests/test_delivery_events.py`:

```python
from studio.schemas.delivery import DeliveryPlan, DeliveryTask
from studio.storage.delivery_plan_service import DeliveryPlanService


def test_delivery_service_records_task_event(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    ws = StudioWorkspace(workspace_root)
    ws.ensure_layout()
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="active",
            task_ids=["task_001"],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement game UI",
            description="Build the screen.",
            owner_agent="dev",
            status="ready",
        )
    )

    service = DeliveryPlanService(workspace_root, project_root=tmp_path)
    event = service.record_task_event(
        "task_001",
        "task_started",
        message="dev started task Implement game UI.",
        metadata={"attempt_count": 1},
    )

    loaded = ws.delivery_task_events.get(event.id)
    assert loaded.task_id == "task_001"
    assert loaded.event_type == "task_started"
    assert loaded.metadata["attempt_count"] == 1
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest tests/test_delivery_events.py::test_delivery_service_records_task_event -q
```

Expected: FAIL because `record_task_event` does not exist.

- [ ] **Step 3: Implement `record_task_event`**

In `DeliveryPlanService`, add:

```python
def record_task_event(
    self,
    task_id: str,
    event_type: str,
    *,
    message: str,
    metadata: dict[str, object] | None = None,
):
    task = self._ws.delivery_tasks.get(task_id)
    event_count = len([
        event for event in self._ws.delivery_task_events.list_all()
        if event.task_id == task_id
    ])
    event = DeliveryTaskEvent(
        id=f"evt_{task_id}_{event_count + 1:04d}",
        task_id=task.id,
        plan_id=task.plan_id,
        requirement_id=task.requirement_id,
        project_id=task.project_id,
        agent=task.owner_agent,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )
    return self._ws.delivery_task_events.save(event)
```

Import `DeliveryTaskEvent`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
uv run pytest tests/test_delivery_events.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add studio/storage/delivery_plan_service.py tests/test_delivery_events.py
git commit -m "feat: record delivery task events"
```

---

### Task 3: Record Events From Delivery Runner And Retry API

**Files:**
- Modify: `studio/runtime/graph.py`
- Modify: `studio/api/routes/delivery.py`
- Test: `tests/test_delivery_graph.py`
- Test: `tests/test_delivery_api.py`

- [ ] **Step 1: Write failing graph event test**

Add to `tests/test_delivery_graph.py`:

```python
def test_delivery_graph_records_task_events(tmp_path: Path, monkeypatch) -> None:
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_delivery_plan(workspace_root)

    class _Agent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state, **kwargs):
            project_dir = Path(str(state.goal["project_dir"]))
            (project_dir / self.role).mkdir(parents=True, exist_ok=True)
            (project_dir / self.role / "output.txt").write_text("done", encoding="utf-8")
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"telemetry": {f"{self.role}_report": {"summary": f"{self.role} done"}}},
                trace={"node": self.role, "fallback_used": False},
            )

    class _Dispatcher:
        def get(self, node_name: str):
            return _Agent(node_name)

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)

    build_delivery_graph().invoke(
        {"workspace_root": str(workspace_root), "project_root": str(project_root), "plan_id": plan_id}
    )

    events = StudioWorkspace(workspace_root).delivery_task_events.list_all()
    event_types = [event.event_type for event in events if event.task_id == "task_art"]

    assert "task_started" in event_types
    assert "agent_session_attached" in event_types
    assert "agent_invocation_started" in event_types
    assert "agent_invocation_completed" in event_types
    assert "file_changes_detected" in event_types
    assert "task_completed" in event_types
```

- [ ] **Step 2: Write failing retry event API test**

Add to `tests/test_delivery_api.py`:

```python
def test_retry_records_task_retried_event(client: TestClient, workspace: Path, planner: FakePlanner) -> None:
    _seed_meeting(workspace, "meet_001")
    gen_resp = client.post(
        "/api/meetings/meet_001/delivery-plan",
        params={"workspace": str(workspace)},
        json={"project_id": "proj_001"},
    )
    task_id = gen_resp.json()["tasks"][0]["id"]
    ws = StudioWorkspace(workspace / ".studio-data")
    task = ws.delivery_tasks.get(task_id)
    ws.delivery_tasks.save(task.model_copy(update={"status": "failed", "last_error": "boom"}))

    resp = client.post(f"/api/delivery-tasks/{task_id}/retry", params={"workspace": str(workspace)}, json={})

    assert resp.status_code == 200
    events = ws.delivery_task_events.list_all()
    assert any(event.task_id == task_id and event.event_type == "task_retried" for event in events)
```

- [ ] **Step 3: Run and verify failures**

Run:

```powershell
uv run pytest tests/test_delivery_graph.py::test_delivery_graph_records_task_events tests/test_delivery_api.py::test_retry_records_task_retried_event -q
```

Expected: FAIL because runner/API do not record these events.

- [ ] **Step 4: Record runner events**

In `studio/runtime/graph.py`, inside `_run_one_task`, call `service.record_task_event`:

- after `started_task = service.start_task(task_id)`: `task_started`
- after lease/session is known through `started_task` and workspace lease lookup: `agent_session_attached`
- immediately before `agent.run(runtime_state)`: `agent_invocation_started`
- immediately after `agent.run(runtime_state)`: `agent_invocation_completed`
- after changed files are known and non-empty: `file_changes_detected`
- after `service.complete_task(...)`: `task_completed`

In the exception handler in `run_delivery_node`, after `service.fail_task(...)`, call:

```python
service.record_task_event(
    task_id,
    "task_failed",
    message=f"Task {task_id} failed: {str(exc) or exc.__class__.__name__}",
    metadata={"exception_type": exc.__class__.__name__},
)
```

- [ ] **Step 5: Record retry event**

In `studio/api/routes/delivery.py`, after `service.retry_task(...)`, call:

```python
service.record_task_event(
    task_id,
    "task_retried",
    message=f"Task {task_id} was reset for retry.",
    metadata={"status": task.status},
)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
uv run pytest tests/test_delivery_graph.py::test_delivery_graph_records_task_events tests/test_delivery_api.py::test_retry_records_task_retried_event -q
```

Expected: PASS.

- [ ] **Step 7: Run broader Delivery tests**

Run:

```powershell
uv run pytest tests/test_delivery_graph.py tests/test_delivery_api.py tests/test_delivery_events.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add studio/runtime/graph.py studio/api/routes/delivery.py tests/test_delivery_graph.py tests/test_delivery_api.py
git commit -m "feat: record delivery runner task events"
```

---

### Task 4: Add Task Events And Session APIs

**Files:**
- Modify: `studio/api/routes/delivery.py`
- Test: `tests/test_delivery_api.py`

- [ ] **Step 1: Write failing API tests**

Add to `tests/test_delivery_api.py`:

```python
def test_get_delivery_task_events_returns_events(client: TestClient, workspace: Path, planner: FakePlanner) -> None:
    _seed_meeting(workspace, "meet_001")
    gen_resp = client.post(
        "/api/meetings/meet_001/delivery-plan",
        params={"workspace": str(workspace)},
        json={"project_id": "proj_001"},
    )
    task_id = gen_resp.json()["tasks"][0]["id"]
    service = DeliveryPlanService(workspace / ".studio-data", project_root=workspace)
    service.record_task_event(task_id, "task_started", message="started")

    resp = client.get(f"/api/delivery-tasks/{task_id}/events", params={"workspace": str(workspace)})

    assert resp.status_code == 200
    assert resp.json()["events"][0]["event_type"] == "task_started"
```

Add a session endpoint test by monkeypatching the SDK loader used by the endpoint:

```python
def test_get_delivery_task_session_returns_agent_messages(
    client: TestClient, workspace: Path, planner: FakePlanner, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_meeting(workspace, "meet_001")
    gen_resp = client.post(
        "/api/meetings/meet_001/delivery-plan",
        params={"workspace": str(workspace)},
        json={"project_id": "proj_001"},
    )
    task = gen_resp.json()["tasks"][0]
    _seed_session(workspace, project_id="proj_001", agent=task["owner_agent"])

    class _Message:
        type = "assistant"
        uuid = "msg_001"
        message = {"content": [{"type": "text", "text": "I implemented the task."}]}

    monkeypatch.setattr("studio.api.routes.delivery.sdk_get_session_messages", lambda *args, **kwargs: [_Message()])

    resp = client.get(f"/api/delivery-tasks/{task['id']}/session", params={"workspace": str(workspace)})

    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task["id"]
    assert data["messages"][0]["content"] == "I implemented the task."
```

- [ ] **Step 2: Run and verify failures**

Run:

```powershell
uv run pytest tests/test_delivery_api.py::test_get_delivery_task_events_returns_events tests/test_delivery_api.py::test_get_delivery_task_session_returns_agent_messages -q
```

Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Implement events endpoint**

Add:

```python
@router.get("/delivery-tasks/{task_id}/events")
async def get_delivery_task_events(task_id: str, workspace: str) -> dict:
    service = _get_service(workspace)
    try:
        service._ws.delivery_tasks.get(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    events = [
        event for event in service._ws.delivery_task_events.list_all()
        if event.task_id == task_id
    ]
    events.sort(key=lambda event: event.created_at)
    return {"events": [event.model_dump() for event in events]}
```

- [ ] **Step 4: Implement session endpoint**

In `studio/api/routes/delivery.py`, import:

```python
from claude_agent_sdk import get_session_messages as sdk_get_session_messages
from studio.agents.profile_loader import AgentProfileLoader
```

Add endpoint:

```python
@router.get("/delivery-tasks/{task_id}/session")
async def get_delivery_task_session(task_id: str, workspace: str) -> dict:
    service = _get_service(workspace)
    try:
        task = service._ws.delivery_tasks.get(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        session = service._ws.sessions.get(f"{task.project_id}_{task.owner_agent}")
    except FileNotFoundError:
        return {
            "task_id": task.id,
            "project_id": task.project_id,
            "agent": task.owner_agent,
            "session_id": None,
            "messages": [],
        }

    profile = AgentProfileLoader().load(task.owner_agent)
    project_root = resolve_project_root(workspace)
    claude_root = profile.claude_project_root
    if not claude_root.is_absolute():
        claude_root = (project_root / claude_root).resolve()

    try:
        sdk_messages = sdk_get_session_messages(session.session_id, directory=str(claude_root))
    except Exception:
        sdk_messages = []

    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "agent": task.owner_agent,
        "session_id": session.session_id,
        "messages": [_delivery_session_message(msg) for msg in sdk_messages],
    }
```

Add helper:

```python
def _delivery_session_message(msg: object) -> dict[str, object]:
    message = getattr(msg, "message", {})
    return {
        "role": str(getattr(msg, "type", "")),
        "content": _extract_content_text(message),
        "uuid": str(getattr(msg, "uuid", "")),
        "blocks": message.get("content", []) if isinstance(message, dict) and isinstance(message.get("content"), list) else [],
    }
```

Reuse or move `_extract_content_text` logic from `studio/api/routes/agents.py`.

- [ ] **Step 5: Run focused API tests**

Run:

```powershell
uv run pytest tests/test_delivery_api.py::test_get_delivery_task_events_returns_events tests/test_delivery_api.py::test_get_delivery_task_session_returns_agent_messages -q
```

Expected: PASS.

- [ ] **Step 6: Run broader API tests**

Run:

```powershell
uv run pytest tests/test_delivery_api.py tests/test_delivery_events.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add studio/api/routes/delivery.py tests/test_delivery_api.py
git commit -m "feat: add delivery task observability APIs"
```

---

### Task 5: Add Frontend Types And API Client

**Files:**
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add API types**

Add:

```ts
export interface DeliveryTaskEvent {
  id: string
  task_id: string
  plan_id: string
  requirement_id: string
  project_id: string
  agent: string
  event_type:
    | 'task_started'
    | 'agent_session_attached'
    | 'agent_invocation_started'
    | 'agent_invocation_completed'
    | 'file_changes_detected'
    | 'task_completed'
    | 'task_failed'
    | 'task_retried'
  message: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface DeliveryTaskSessionMessage {
  role: string
  content: string
  uuid: string
  blocks: unknown[]
}

export interface DeliveryTaskSession {
  task_id: string
  project_id: string
  agent: string
  session_id: string | null
  messages: DeliveryTaskSessionMessage[]
}
```

- [ ] **Step 2: Add API client methods**

Add to `deliveryApi`:

```ts
getTaskEvents: (workspace: string, taskId: string): Promise<{ events: DeliveryTaskEvent[] }> =>
  apiRequest(`/delivery-tasks/${taskId}/events`, 'get', {
    params: { workspace },
  }) as Promise<{ events: DeliveryTaskEvent[] }>,

getTaskSession: (workspace: string, taskId: string): Promise<DeliveryTaskSession> =>
  apiRequest(`/delivery-tasks/${taskId}/session`, 'get', {
    params: { workspace },
  }) as Promise<DeliveryTaskSession>,
```

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add web/src/lib/api.ts
git commit -m "feat: add delivery observability frontend APIs"
```

---

### Task 6: Build Delivery Task Detail Drawer

**Files:**
- Create: `web/src/components/board/DeliveryTaskDetailDrawer.tsx`
- Modify: `web/src/components/board/DeliveryTaskCard.tsx`
- Modify: `web/src/pages/DeliveryBoard.tsx`

- [ ] **Step 1: Create drawer component**

Create `DeliveryTaskDetailDrawer.tsx` with props:

```ts
interface DeliveryTaskDetailDrawerProps {
  task: DeliveryTask | null
  workspace: string
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

Use a simple fixed right drawer or existing Dialog primitives. Include tabs in component-local state:

```ts
const [tab, setTab] = useState<'overview' | 'events' | 'session' | 'artifacts'>('overview')
```

- [ ] **Step 2: Fetch events and session**

Inside the drawer:

```tsx
const eventsQuery = useQuery({
  queryKey: ['delivery-task-events', workspace, task?.id],
  queryFn: () => deliveryApi.getTaskEvents(workspace, task!.id),
  enabled: open && Boolean(task),
  refetchInterval: task?.status === 'in_progress' ? 2000 : false,
})

const sessionQuery = useQuery({
  queryKey: ['delivery-task-session', workspace, task?.id],
  queryFn: () => deliveryApi.getTaskSession(workspace, task!.id),
  enabled: open && Boolean(task) && tab === 'session',
  refetchInterval: task?.status === 'in_progress' && tab === 'session' ? 3000 : false,
})
```

- [ ] **Step 3: Render Overview tab**

Show:

- task id
- owner agent
- status
- attempt count
- description
- acceptance criteria
- dependencies
- checks/follow-ups when available through task fields
- last error if present

- [ ] **Step 4: Render Events tab**

Render `eventsQuery.data?.events ?? []` sorted by `created_at`.

Each row shows:

- event type
- created time
- message
- collapsed metadata JSON using `<details>`

- [ ] **Step 5: Render Agent Session tab**

Render:

- session id if present
- messages in chronological order
- role badge
- content text
- `<details>` for non-empty `blocks`

Empty state:

```tsx
No Claude session transcript is available yet.
```

- [ ] **Step 6: Render Artifacts tab**

Show:

- `task.output_artifact_ids`
- changed file paths if they are available from existing task data
- empty state if no artifacts

- [ ] **Step 7: Wire card click into board**

In `DeliveryBoard.tsx`, add selected task state:

```tsx
const [selectedTask, setSelectedTask] = useState<DeliveryTask | null>(null)
```

Pass `onOpen={() => setSelectedTask(task)}` or `onClick` into `DeliveryTaskCard`.

Render:

```tsx
<DeliveryTaskDetailDrawer
  task={selectedTask}
  workspace={workspace}
  open={Boolean(selectedTask)}
  onOpenChange={(open) => { if (!open) setSelectedTask(null) }}
/>
```

In `DeliveryTaskCard`, make the root card clickable while keeping start/retry buttons with `stopPropagation`.

- [ ] **Step 8: Run frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add web/src/components/board/DeliveryTaskDetailDrawer.tsx web/src/components/board/DeliveryTaskCard.tsx web/src/pages/DeliveryBoard.tsx
git commit -m "feat: add delivery task detail drawer"
```

---

### Task 7: Final Verification

**Files:**
- No new files expected

- [ ] **Step 1: Run backend tests**

Run:

```powershell
uv run pytest tests/test_delivery_graph.py tests/test_delivery_api.py tests/test_delivery_events.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full backend tests if time allows**

Run:

```powershell
uv run pytest tests -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 4: Inspect git diff**

Run:

```powershell
git status --short
git log --oneline -5
```

Expected:

- only intended files changed
- commits are split by task as above

---

## Assumptions

- The implementation will happen in a fresh worktree created by the user.
- Automatic retry policy is intentionally out of scope for this iteration.
- The first session endpoint can reuse the current simplified Claude transcript extraction.
- Tool call blocks are best-effort: preserve structured blocks when available, but do not block the feature if only text content is available.
- The drawer uses polling while open instead of live token streaming.

## Self-Review

- Spec coverage: event persistence, runner events, retry events, task APIs, session API, drawer UI, and missing transcript fallback are covered.
- Placeholder scan: no deferred placeholders remain.
- Type consistency: `DeliveryTaskEvent`, event type names, API method names, and drawer tab names are consistent across tasks.
