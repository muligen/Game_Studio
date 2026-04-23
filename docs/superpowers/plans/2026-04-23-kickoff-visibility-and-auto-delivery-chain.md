# Kickoff Visibility And Auto Delivery Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kickoff visible to users and automatically chain successful meetings into delivery-plan generation and board navigation.

**Architecture:** Extend the kickoff API to return a compact meeting snapshot, then update the clarification dialog to run a small frontend state machine for kickoff progress, delivery generation, and success/failure result display. Keep the backend synchronous and reuse the existing delivery-plan API rather than introducing background orchestration.

**Tech Stack:** FastAPI, Pydantic, React, TypeScript, TanStack Query, Vite, pytest

---

## File Structure

### Backend

- Modify: `studio/api/routes/clarifications.py`
  - Extend kickoff response payload with a compact meeting snapshot
  - Preserve current kickoff execution semantics

### Frontend

- Modify: `web/src/lib/api.ts`
  - Extend kickoff response typings to include meeting snapshot
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`
  - Add kickoff progress/result state machine
  - Auto-call delivery plan generation after kickoff success
  - Surface kickoff and delivery errors separately
  - Navigate to delivery board on success

### Tests

- Modify: `tests/test_clarification_routes.py`
  - Cover kickoff response snapshot contract
- Optional/If present later: frontend tests for dialog behavior

---

### Task 1: Extend Kickoff API Response

**Files:**
- Modify: `studio/api/routes/clarifications.py`
- Test: `tests/test_clarification_routes.py`

- [ ] **Step 1: Write the failing backend test**

Add a test in `tests/test_clarification_routes.py` asserting kickoff returns `meeting` data along with `project_id`, `requirement_id`, `meeting_id`, and `status`.

Suggested test shape:

```python
async def test_kickoff_returns_meeting_snapshot(client, workspace_with_ready_session):
    response = await client.post(
        f"/api/clarifications/requirements/{req_id}/kickoff",
        params={"workspace": str(workspace)},
        json={"session_id": session_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "kickoff_complete"
    assert payload["meeting_id"]
    assert payload["project_id"]
    assert payload["meeting"]["id"] == payload["meeting_id"]
    assert "summary" in payload["meeting"]
    assert "attendees" in payload["meeting"]
    assert "consensus_points" in payload["meeting"]
    assert "conflict_points" in payload["meeting"]
    assert "pending_user_decisions" in payload["meeting"]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
uv run pytest tests/test_clarification_routes.py -k kickoff_returns_meeting_snapshot -q
```

Expected:

- FAIL because kickoff currently does not include a `meeting` snapshot in the response

- [ ] **Step 3: Implement the minimal backend change**

Update `start_kickoff` in `studio/api/routes/clarifications.py` to extract the meeting minutes result and return a compact snapshot.

Target implementation shape:

```python
minutes = result.get("minutes", {})
meeting_id = minutes.get("id", "")

meeting_snapshot = {
    "id": meeting_id,
    "title": minutes.get("title", ""),
    "summary": minutes.get("summary", ""),
    "attendees": list(minutes.get("attendees", [])),
    "consensus_points": list(minutes.get("consensus", [])),
    "conflict_points": list(minutes.get("conflicts", [])),
    "pending_user_decisions": list(minutes.get("pending_user_decisions", [])),
}

return {
    "project_id": project_id,
    "requirement_id": req_id,
    "meeting_id": meeting_id,
    "status": "kickoff_complete",
    "meeting": meeting_snapshot,
}
```

Adjust field names to match the actual `MeetingMinutes` schema if the graph output uses different keys.

- [ ] **Step 4: Run the focused backend test and verify it passes**

Run:

```powershell
uv run pytest tests/test_clarification_routes.py -k kickoff_returns_meeting_snapshot -q
```

Expected:

- PASS

- [ ] **Step 5: Run the full clarification route test file**

Run:

```powershell
uv run pytest tests/test_clarification_routes.py -q
```

Expected:

- All clarification route tests pass

- [ ] **Step 6: Commit**

```powershell
git add studio/api/routes/clarifications.py tests/test_clarification_routes.py
git commit -m "Return meeting snapshot from kickoff"
```

---

### Task 2: Add Kickoff Response Typings To Frontend API

**Files:**
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add or update the kickoff response types**

Add a compact meeting snapshot type and update the kickoff API return type.

Suggested shape:

```ts
export interface KickoffMeetingSnapshot {
  id: string
  title: string
  summary: string
  attendees: string[]
  consensus_points: string[]
  conflict_points: string[]
  pending_user_decisions: string[]
}

export interface KickoffResponse {
  project_id: string
  requirement_id: string
  meeting_id: string
  status: string
  meeting: KickoffMeetingSnapshot
}
```

- [ ] **Step 2: Update `clarificationsApi.kickoff` to return the shared type**

Replace the inline return type with `Promise<KickoffResponse>`.

Suggested shape:

```ts
kickoff: (
  workspace: string,
  requirementId: string,
  sessionId: string,
): Promise<KickoffResponse> =>
  apiRequest(`/clarifications/requirements/${requirementId}/kickoff`, 'post', {
    params: { workspace },
    body: JSON.stringify({ session_id: sessionId }),
    headers: { 'Content-Type': 'application/json' },
  }) as Promise<KickoffResponse>,
```

- [ ] **Step 3: Run TypeScript build to verify typings**

Run:

```powershell
npm --prefix web run build
```

Expected:

- Build may still fail because dialog code has not been updated yet, but there should be no syntax/type errors introduced by the new API types themselves

- [ ] **Step 4: Commit**

```powershell
git add web/src/lib/api.ts
git commit -m "Add kickoff meeting snapshot types"
```

---

### Task 3: Add Kickoff Progress And Result States In Clarification Dialog

**Files:**
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] **Step 1: Define minimal local UI state**

Add local state for kickoff workflow status and result payload.

Suggested state:

```ts
type KickoffUiState =
  | { phase: 'idle' }
  | { phase: 'kickoff_running' }
  | { phase: 'kickoff_failed'; error: string }
  | { phase: 'kickoff_completed'; result: KickoffResponse }
  | { phase: 'delivery_generating'; result: KickoffResponse }
  | { phase: 'delivery_failed'; result: KickoffResponse; error: string }
```

- [ ] **Step 2: Update kickoff mutation behavior**

Change kickoff mutation so it no longer closes the dialog on success.

Target behavior:

- before request: set `kickoff_running`
- on success: store kickoff result and transition to `delivery_generating`
- on error: store `kickoff_failed`

Suggested shape:

```ts
const [kickoffUi, setKickoffUi] = useState<KickoffUiState>({ phase: 'idle' })
```

```ts
const kickoffMutation = useMutation({
  mutationFn: () => clarificationsApi.kickoff(workspace, requirementId, session!.id),
  onMutate: () => setKickoffUi({ phase: 'kickoff_running' }),
  onSuccess: (result) => setKickoffUi({ phase: 'delivery_generating', result }),
  onError: (error) =>
    setKickoffUi({
      phase: 'kickoff_failed',
      error: error instanceof Error ? error.message : 'Kickoff failed.',
    }),
})
```

- [ ] **Step 3: Render a distinct kickoff progress/result panel**

In the dialog body, branch on `kickoffUi.phase`.

Minimum render requirements:

- `idle`: existing chat + context preview
- `kickoff_running`: title, loading text, disabled actions
- `delivery_generating`: kickoff succeeded, now generating delivery plan
- `kickoff_failed`: show kickoff error and allow retry
- `delivery_failed`: show meeting result summary plus retry delivery action

Suggested minimal success panel contents:

```tsx
<div className="space-y-3">
  <Badge>Kickoff Complete</Badge>
  <p>{kickoffUi.result.meeting.summary}</p>
  <div>
    <p>Meeting ID: {kickoffUi.result.meeting_id}</p>
    <p>Project ID: {kickoffUi.result.project_id}</p>
  </div>
</div>
```

- [ ] **Step 4: Disable chat input during kickoff/delivery processing**

When `kickoffUi.phase` is not `idle` or `kickoff_failed`, disable:

- message input
- send button
- kickoff button

This prevents duplicate kickoff submissions and confusing chat interactions while the meeting chain runs.

- [ ] **Step 5: Run frontend build and verify it compiles**

Run:

```powershell
npm --prefix web run build
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```powershell
git add web/src/components/common/RequirementClarificationDialog.tsx
git commit -m "Show kickoff progress and result states"
```

---

### Task 4: Auto-Generate Delivery Plan After Kickoff Success

**Files:**
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] **Step 1: Add delivery generation mutation**

Create a dedicated mutation using `deliveryApi.generatePlan`.

Suggested shape:

```ts
const deliveryMutation = useMutation({
  mutationFn: ({ meetingId, projectId }: { meetingId: string; projectId: string }) =>
    deliveryApi.generatePlan(workspace, meetingId, projectId),
})
```

- [ ] **Step 2: Trigger delivery generation after kickoff success**

Use `useEffect` or kickoff `onSuccess` chaining to start delivery generation when kickoff succeeds.

Preferred shape:

```ts
useEffect(() => {
  if (kickoffUi.phase !== 'delivery_generating') return
  deliveryMutation.mutate(
    {
      meetingId: kickoffUi.result.meeting_id,
      projectId: kickoffUi.result.project_id,
    },
    {
      onSuccess: () => {
        navigate('/delivery')
      },
      onError: (error) => {
        setKickoffUi({
          phase: 'delivery_failed',
          result: kickoffUi.result,
          error: error instanceof Error ? error.message : 'Delivery generation failed.',
        })
      },
    },
  )
}, [kickoffUi])
```

Use the app's existing routing mechanism; if React Router hooks are already available, use `useNavigate`. If not, adapt to the current router pattern in `web/src/App.tsx`.

- [ ] **Step 3: Add retry action for delivery generation**

In the `delivery_failed` UI state, add a button that retries:

```ts
deliveryMutation.mutate({
  meetingId: kickoffUi.result.meeting_id,
  projectId: kickoffUi.result.project_id,
})
```

- [ ] **Step 4: Show a lightweight success bridge before navigation if needed**

If immediate navigation feels abrupt, show a short success message such as:

```tsx
<p>Kickoff finished. Generating delivery tasks...</p>
```

Do not introduce timers unless necessary; synchronous chain completion is acceptable.

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

Manual expected behavior:

- open clarify dialog
- click `Start Kickoff Meeting`
- see kickoff progress state
- after kickoff, delivery generation runs automatically
- UI lands on `/delivery`
- if decision gate exists, it is visible on the board

- [ ] **Step 7: Commit**

```powershell
git add web/src/components/common/RequirementClarificationDialog.tsx
git commit -m "Auto-chain kickoff into delivery generation"
```

---

### Task 5: Polish Failure UX And Meeting Discoverability

**Files:**
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`
- Optionally modify: `web/src/lib/api.ts`

- [ ] **Step 1: Add explicit separation between kickoff and delivery failures**

Ensure the UI distinguishes:

- kickoff failed before any meeting existed
- kickoff succeeded but delivery generation failed

Suggested user copy:

```tsx
<p className="text-sm text-red-600">Kickoff completed, but delivery task generation failed.</p>
```

- [ ] **Step 2: Add a meeting result summary section**

In `kickoff_completed` or `delivery_failed` states, show:

- meeting summary
- attendees
- first few consensus points
- first few conflict points

Suggested rendering shape:

```tsx
<div className="space-y-2 text-sm">
  <p className="font-medium">Meeting Summary</p>
  <p>{result.meeting.summary}</p>
  <p>Attendees: {result.meeting.attendees.join(', ')}</p>
</div>
```

- [ ] **Step 3: Add meeting result actions**

Provide visible actions:

- `Open Delivery Board`
- `Retry Generate Delivery Plan` when relevant

If a meeting minutes page or API detail route is already convenient to open later, add a placeholder secondary button only if it can be wired cleanly in this task. Do not invent a fake destination.

- [ ] **Step 4: Run verification**

Run:

```powershell
npm --prefix web run build
```

```powershell
uv run pytest tests/test_clarification_routes.py -q
```

Expected:

- both pass

- [ ] **Step 5: Commit**

```powershell
git add web/src/components/common/RequirementClarificationDialog.tsx web/src/lib/api.ts tests/test_clarification_routes.py
git commit -m "Polish kickoff result and failure states"
```

---

## Plan Self-Review

### Spec Coverage

- visible kickoff progress state: covered in Task 3
- meeting snapshot in kickoff response: covered in Task 1
- automatic delivery generation: covered in Task 4
- delivery failure retry: covered in Task 4 and Task 5
- meeting result discoverability: covered in Task 3 and Task 5

### Placeholder Scan

- No `TBD`, `TODO`, or deferred implementation placeholders remain in task steps
- Commands and target files are specified for each task

### Type Consistency

- `KickoffResponse` is introduced in Task 2 and reused consistently in later tasks
- `meeting_id` and `project_id` are the identifiers used throughout the plan

---

Plan complete and saved to `docs/superpowers/plans/2026-04-23-kickoff-visibility-and-auto-delivery-chain.md`.

Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
