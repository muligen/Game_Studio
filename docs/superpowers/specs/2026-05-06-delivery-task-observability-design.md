# Delivery Task Observability And Session Timeline Design

## Goal

Make Delivery execution inspectable while tasks are running and after they finish.

Users should be able to open the Delivery Board and answer:

- Which agents are currently working?
- Which task is each agent executing?
- What happened during the task execution?
- Which Claude session did the task use?
- What did the agent say, what tools did it call, and what was the last output before failure?

## Current State

Delivery already has a DAG runner, shared Agent Pool visibility, filesystem change tracking, task failure persistence, and manual retry.

What is still missing:

- no persisted per-task event timeline
- no task detail view on the Delivery Board
- no direct link from a Delivery task to its Claude session transcript
- no display of Claude Code turns or tool calls inside the Delivery task context

The current Agent Chat page can read agent session messages by `project_id` and `agent`, but the Delivery Board does not expose that ability per task.

## Product Design

### Delivery Task Detail Drawer

Clicking a task card should open a detail drawer.

The drawer has four tabs:

- `Overview`: task description, owner, status, attempts, dependencies, acceptance criteria, changed files, checks, follow-ups, last error
- `Events`: chronological task execution events
- `Agent Session`: Claude session messages and tool activity for the task agent
- `Artifacts`: output artifact paths and changed files

The drawer should work for `ready`, `in_progress`, `done`, and `failed` tasks. Empty states should be explicit and calm, for example "No events recorded yet."

### Task Event Timeline

The backend should persist a `DeliveryTaskEvent` record for important runner milestones:

- `task_started`
- `agent_session_attached`
- `agent_invocation_started`
- `agent_invocation_completed`
- `file_changes_detected`
- `task_completed`
- `task_failed`
- `task_retried`

Events are task-scoped and stored under `.studio-data/delivery_task_events/`.

Events should be display-friendly by default, with optional metadata for debugging. Metadata can include session id, agent role, changed files, exception type, traceback excerpt, and execution result id.

### Agent Session Timeline

Add a task-scoped API that returns the Claude session attached to the task:

- `GET /api/delivery-tasks/{task_id}/session`

The response should include:

- `task_id`
- `project_id`
- `agent`
- `session_id`
- `messages`

Messages should reuse the existing Claude transcript loading behavior from `/api/agents/{project_id}/{agent}/messages`, but returned through a Delivery task entry point. The first version can return the same simplified message shape currently used by Agent Chat: role, content, and uuid.

Tool call detail should be best-effort in v1:

- if the SDK message extraction exposes tool blocks, preserve them as structured `blocks`
- if only text extraction is available, show the text content and leave tool blocks empty

The UI should not block on missing or unreadable transcripts. It should show an empty state and keep the task drawer usable.

### Real-Time Feedback

When task status or task events change, the backend should broadcast websocket `entity_changed` messages so the board refetches:

- `delivery_task`
- `delivery_task_event`
- `pool`

The first implementation can combine websocket invalidation with lightweight polling while a task drawer is open. This avoids building a streaming transport before the event model is stable.

## Data Model

Add `DeliveryTaskEvent`:

```json
{
  "id": "evt_task_dev_001_0001",
  "task_id": "task_dev_001",
  "plan_id": "plan_001",
  "requirement_id": "req_001",
  "project_id": "proj_001",
  "agent": "dev",
  "event_type": "agent_invocation_started",
  "message": "dev started implementing the Snake MVP UI.",
  "metadata": {
    "session_id": "sess_dev",
    "attempt_count": 1
  },
  "created_at": "2026-05-06T..."
}
```

Add board/API optional fields only where they directly support the drawer:

- task event list endpoint
- task session endpoint
- optional execution result details in task board response if already cheap to include

Do not change the Delivery runner DAG semantics in this iteration.

## Backend Design

Add a small event recording helper in Delivery execution code. The helper should:

- create monotonic event ids using timestamp or sequence
- save to `StudioWorkspace.delivery_task_events`
- attempt websocket broadcast when running in an API/event-loop context, but never fail the runner if broadcast fails

Delivery runner capture points:

- before `service.start_task`: no persisted event required, because task may not be valid yet
- after `service.start_task`: `task_started` and `agent_session_attached`
- before `agent.run`: `agent_invocation_started`
- after `agent.run`: `agent_invocation_completed`
- after diff detection: `file_changes_detected` if files changed
- after `service.complete_task`: `task_completed`
- in exception handler after `service.fail_task`: `task_failed`
- in retry API after `service.retry_task`: `task_retried`

Add task detail APIs:

- `GET /api/delivery-tasks/{task_id}/events`
- `GET /api/delivery-tasks/{task_id}/session`

The session endpoint should find the task, then find the project-agent session through `SessionRegistry` or workspace sessions. It should call the same transcript-loading path used by the existing agent messages API.

## Frontend Design

Delivery Board should keep the current board layout and add detail inspection.

Task card changes:

- clicking a task card opens `DeliveryTaskDetailDrawer`
- `Start Agent Work` and `Retry Agent Work` buttons keep stopping propagation
- failed cards continue showing last error

New `DeliveryTaskDetailDrawer`:

- fetches task events when open
- fetches task session when `Agent Session` tab is selected or when open, whichever is simpler
- uses compact tabs, not nested cards
- refreshes every 2 seconds while task is `in_progress`

Agent Session tab:

- render messages chronologically
- show role badge and content
- show tool blocks if present
- if no transcript exists, show "No Claude session transcript is available yet."

Events tab:

- render event type, timestamp, message
- expose metadata in a collapsed JSON block

## Acceptance Criteria

1. A running Delivery task creates persisted task events.
2. A failed Delivery task records a `task_failed` event and remains retryable.
3. Retrying a failed task records a `task_retried` event.
4. Delivery Board task cards can open a detail drawer.
5. The drawer shows Overview, Events, Agent Session, and Artifacts tabs.
6. The Events tab shows persisted task events in chronological order.
7. The Agent Session tab can show the Claude session messages for the task's agent.
8. Missing transcript data does not break the drawer.
9. Backend tests cover event persistence, failure events, retry events, and session endpoint behavior.
10. Frontend build passes.

## Out Of Scope

- automatic retry policy
- live token streaming
- editing task prompts from the drawer
- changing Delivery DAG scheduling
- replacing Langfuse as the deep observability source

## Implementation Notes

Prefer small, focused additions:

- schema and storage first
- service/runtime event recording second
- API endpoints third
- drawer UI last

This keeps the next implementation worktree easy to test and easy to commit in slices.
