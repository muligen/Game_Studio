# Auto Design Workflow Design

**Date:** 2026-04-15
**Status:** Draft

## Summary

Wire the design workflow into the Web UI so that when a user creates a requirement, an Agent automatically picks it up, generates a design document via Claude, and presents it for review. The user can then approve, edit-and-approve, or send back with feedback that triggers a rework cycle.

## Motivation

The current `POST /api/workflows/run-design` endpoint is a stub — it writes placeholder data (`core_rules: ["rule 1"]`) and never calls an Agent. The Web UI has no way to trigger workflows. This design connects the existing LangGraph design graph and Claude-backed `DesignAgent` to the Web UI via a background polling mechanism.

## Data Flow

```
User creates requirement in Web UI (status: draft)
         |
         v
  +------------------------------------------+
  | Background poller (10s)                  |
  | Scans for:                               |
  |   - requirements with status "draft"     |
  |   - requirements with status "designing" |
  |     AND design_doc in "sent_back" status |
  +--------------------+---------------------+
                       | discovers eligible requirement
                       v
  First-time (draft):               Rework (designing + sent_back doc):
    1. draft -> designing             1. designing (already set)
    2. Invoke design graph            2. Invoke design graph with sent_back_reason
    3. Agent generates doc            3. Agent revises doc based on feedback
    4. -> pending_user_review         4. -> pending_user_review
                       |
                       v
  Web UI auto-refreshes via WebSocket, shows design doc with review controls
                       |
           +-----------+-----------+
           |                       |
       [Approve]              [Send Back + reason]
           |                       |
           v                       v
      approved               designing (requirement)
                             sent_back (design doc, reason stored)
                                      |
                                      v
                             Poller picks up rework -> back to pending_user_review
```

## Components

### 1. WorkflowPoller (`studio/runtime/poller.py`)

A background asyncio task that scans the workspace for eligible requirements:
- **New designs:** requirements with status `draft`
- **Reworks:** requirements with status `designing` that have a `design_doc_id` pointing to a design doc with status `sent_back`

```python
class WorkflowPoller:
    interval: int          # Polling interval in seconds, default 10
    workspace_path: Path   # Workspace to scan

    async def start()      # Called from FastAPI lifespan, starts the loop
    async def stop()       # Graceful shutdown
    async def _tick()      # Single scan: find eligible requirements -> execute one by one
```

**Deduplication:** Single-threaded sequential execution. Each `_tick()` scans for eligible requirements and processes them one at a time. For new designs, the first action is `transition_requirement(req, "designing")` followed by `save()`. For reworks, the requirement is already in `designing` state. In both cases, the requirement status changes during execution so subsequent polls skip it.

**Configuration:** `GAME_STUDIO_POLL_INTERVAL` env var (default 10 seconds).

**Scoping:** Polls a single workspace path configured at startup. Default: `.runtime-data` in the project root.

### 2. DesignWorkflowExecutor (`studio/runtime/executor.py`)

Wraps the LangGraph design graph invocation, connecting it to storage and WebSocket broadcasting.

```python
class DesignWorkflowExecutor:
    def run(workspace: StudioWorkspace, requirement: RequirementCard) -> dict:
        # 1. Transition requirement to "designing" (skip if already designing = rework)
        # 2. Build input state for design graph (include sent_back_reason if rework)
        # 3. Call build_design_graph().invoke(state)
        # 4. Extract design doc from graph output
        # 5. Save/overwrite design doc in storage
        # 6. Transition requirement to "pending_user_review"
        # 7. Update requirement with design_doc_id link
        # 8. Broadcast WebSocket events
        # 9. Return result dict
```

**Rework support:** When re-executing for a sent-back design (requirement in `designing` with existing design doc in `sent_back` status), the executor loads the existing design doc, includes the `sent_back_reason` in the Agent prompt, and regenerates the design content. The existing design doc is overwritten with the new version.

**Fallback:** If `build_design_graph()` is unavailable or Claude is disabled, the graph's built-in deterministic fallback produces a placeholder design doc so the flow does not block.

### 3. Updated API Endpoints

**`POST /api/workflows/run-design`** — Replaces the stub implementation with a call to `DesignWorkflowExecutor`. Both manual API triggers and automatic poller triggers now go through the same executor.

**`POST /api/design-docs/{id}/send-back`** — Add required `reason: str` body parameter. The reason is stored in `DesignDoc.sent_back_reason`.

### 4. Schema Changes

**`DesignDoc`** — Add optional field:
- `sent_back_reason: str | None = None` — Populated when the doc is sent back for revision. Passed to the Agent on rework.

### 5. Frontend Changes

**DesignEditor page (`web/src/pages/DesignEditor.tsx`):**

1. **Editable fields:** `core_rules`, `acceptance_criteria`, `open_questions` become editable text areas (one item per line). A "Save" button calls `PATCH /api/design-docs/{id}` to persist edits.

2. **Send-back with reason:** The "Send Back" button opens a dialog with a required textarea. On submit, calls `POST /api/design-docs/{id}/send-back` with `{ reason: "..." }`.

3. **Edit-and-approve flow:** User edits fields, saves, then clicks "Approve". The approval reads the latest saved version.

**RequirementsBoard page (`web/src/pages/RequirementsBoard.tsx`):**

- RequirementCard: when `design_doc_id` is set, show a "View Design" link that navigates to `/design-docs/{id}`.

### 6. Poller Integration with FastAPI

```python
# studio/api/main.py lifespan
@asynccontextmanager
async def lifespan(app):
    poller = WorkflowPoller(workspace_path=Path(".runtime-data"))
    task = asyncio.create_task(poller.start())
    yield
    await poller.stop()
    task.cancel()
```

The poller starts when the backend starts and stops gracefully on shutdown.

## Error Handling

| Scenario | Strategy |
|----------|----------|
| Claude call fails | Graph-internal deterministic fallback (existing mechanism) |
| Graph execution throws | Catch exception, transition requirement back to `draft`, log error, continue to next requirement on next tick |
| Storage write fails | Exception propagates to poller, logged, requirement stays in `designing` state and will not be re-picked up (manual intervention needed) |
| Poller crashes | FastAPI lifespan restart not automatic; logs the error. User restarts the server. |

## What Does NOT Change

- `build_design_graph()` in `studio/runtime/graph.py` — reused as-is
- `DesignAgent` in `studio/agents/design.py` — reused as-is
- WebSocket broadcast mechanism — reused as-is
- State machine transitions in `studio/domain/requirement_flow.py` — reused as-is (`pending_user_review` -> `designing` already allowed)
- Kanban board components — already support all status columns

## Future Extensions (Out of Scope)

- Dev/QA/Quality workflow auto-execution (same pattern, different graph)
- Multi-workspace polling
- Concurrent graph execution with worker pool
- Retry limits for repeatedly failing requirements
