# Clarify Kickoff Timeline Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move kickoff-running and kickoff-complete states out of the clarification dialog and into timeline card progress plus a dedicated kickoff detail dialog.

**Architecture:** Persist kickoff task progress on the backend, derive a frontend iteration phase from requirement plus clarification/kickoff state, show compact progress on the timeline card, and use a focused detail dialog for running/failed/completed meetings. The clarification dialog remains only for brief collection and explicit failed-kickoff editing.

**Tech Stack:** FastAPI/Pydantic backend, LangGraph runtime, React/TypeScript frontend, TanStack Query polling, existing UI primitives.

---

### Task 1: Backend Kickoff Progress Contract

**Files:**
- Modify: `studio/schemas/kickoff_task.py`
- Modify: `studio/storage/kickoff_service.py`
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_clarification_routes.py`
- Test: `tests/test_meeting_graph.py`

- [ ] Add progress fields to `KickoffTask`: `current_node`, `completed_nodes`, `active_agents`, `progress_events`, `started_at`, `updated_at`.
- [ ] Record running and completed meeting graph nodes while kickoff executes.
- [ ] Mark delivery plan as its own progress step.
- [ ] Add tests that kickoff task polling returns progress and graph execution records node completion.
- [ ] Run `uv run pytest tests/test_clarification_routes.py tests/test_meeting_graph.py tests/test_clarification_schemas.py -q`.

### Task 2: Frontend Meeting Graph Components

**Files:**
- Create: `web/src/components/common/MeetingGraphProgress.tsx`
- Modify: `web/src/lib/api.ts`

- [ ] Add `KickoffTaskStatus` progress fields to the API type.
- [ ] Create a reusable graph component that renders `Prepare`, `Agent Opinions`, `Summarize`, `Discussion`, `Minutes`, and `Delivery Plan`.
- [ ] Show done, active, failed, skipped, and pending states from the task progress contract.
- [ ] Run `npm run build` in `web`.

### Task 3: Kickoff Detail Dialog

**Files:**
- Create: `web/src/components/common/KickoffDetailDialog.tsx`
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] Move running/failed/completed kickoff display from `RequirementClarificationDialog` into `KickoffDetailDialog`.
- [ ] Expose actions: `Retry Kickoff`, `Edit Clarification`, `View Meeting Transcript`, `View Meeting Minutes`, `Open Delivery Board`, and `Retry Generate Delivery Plan`.
- [ ] Keep `Edit Clarification` visible only for kickoff failure.
- [ ] Ensure `kickoff_running` never opens the clarification chat as the primary surface.
- [ ] Run `npm run build` in `web`.

### Task 4: Timeline Card Entry Points

**Files:**
- Modify: `web/src/pages/RequirementsBoard.tsx`
- Modify: `web/src/lib/product-workbench.ts`

- [ ] Add derived frontend phase labels for `clarifying`, `ready_for_kickoff`, `kickoff_running`, `kickoff_failed`, `kickoff_complete`, and `delivery_ready`.
- [ ] Show compact meeting graph on the active timeline card when a kickoff task exists.
- [ ] Change card action rules: `Continue Clarifying`, `Start Kickoff`, `View Meeting`, `Retry Kickoff`, `Edit Clarification`, `View Delivery`.
- [ ] Poll or fetch clarification session/kickoff task data needed by the card without requiring the old clarification dialog.
- [ ] Run `npm run build` in `web`.

### Task 5: Final Verification

**Files:**
- No new files.

- [ ] Run backend tests: `uv run pytest tests/test_clarification_routes.py tests/test_meeting_graph.py tests/test_clarification_schemas.py -q`.
- [ ] Run frontend build: `npm run build` from `web`.
- [ ] Confirm `git status --short` shows only intentional files plus pre-existing unrelated dirty files.
