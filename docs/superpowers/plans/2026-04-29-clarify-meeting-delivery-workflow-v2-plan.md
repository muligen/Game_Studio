# Clarify Meeting Delivery Workflow V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement one coherent Clarify Brief -> Kickoff Meeting -> Delivery workflow so timeline cards, clarification, meeting detail, and delivery entry points all follow one derived phase model.

**Architecture:** Add a single frontend workflow derivation module that maps requirement, clarification session, kickoff task, and delivery summary into a phase, progress steps, and allowed actions. Refactor the requirements timeline to render only that derived state, keep clarification focused on brief editing, and keep meeting detail responsible for meeting execution plus delivery generation recovery.

**Tech Stack:** React, TypeScript, TanStack Query, existing FastAPI/Pydantic APIs, existing kickoff task progress contract.

---

### Task 1: Workflow Derivation Module

**Files:**
- Create: `web/src/lib/requirement-workflow.ts`
- Modify: `web/src/pages/RequirementsBoard.tsx`

- [ ] Define `RequirementWorkflowPhase`, `WorkflowAction`, `WorkflowProgressStep`, and `RequirementWorkflowState`.
- [ ] Implement `deriveRequirementWorkflowState({ requirement, clarificationSession, kickoffTask, deliverySummary })`.
- [ ] Encode all phase/action rules from the V2 spec in this function.
- [ ] Add lightweight assertion helpers in the module so invalid action ids are impossible at compile time.
- [ ] Run `npm run build` from `web`.

### Task 2: Timeline Uses Derived Workflow State

**Files:**
- Modify: `web/src/pages/RequirementsBoard.tsx`
- Modify: `web/src/components/common/MeetingGraphProgress.tsx`

- [ ] Replace raw status checks in `ActiveIterationActions` with `deriveRequirementWorkflowState`.
- [ ] Render a three-stage Clarify -> Meeting -> Delivery progress strip from `workflow.progressSteps`.
- [ ] Render compact meeting node graph only when the derived phase is a meeting/delivery-generation phase.
- [ ] Route primary and secondary actions by action id instead of hand-written phase checks in the component.
- [ ] Run `npm run build` from `web`.

### Task 3: Clarify Surface Owns Only Brief Work

**Files:**
- Modify: `web/src/components/common/RequirementClarificationDialog.tsx`

- [ ] Ensure opening clarification for a `kickoff_started` session closes immediately through `onKickoffStarted`.
- [ ] Remove visible meeting-running and delivery-ready pathways from the normal clarify entry path.
- [ ] Keep `Edit Clarification` only as an explicit recovery path supplied by the timeline/meeting detail.
- [ ] Keep `Start Kickoff Meeting` only when readiness is true and no kickoff is active.
- [ ] Run `npm run build` from `web`.

### Task 4: Meeting Detail Owns Meeting and Delivery Handoff

**Files:**
- Modify: `web/src/components/common/KickoffDetailDialog.tsx`

- [ ] Rename visible wording from Kickoff to Meeting where appropriate: `Retry Meeting`, `Meeting Running`, `Meeting Failed`.
- [ ] Add `Generate Delivery` action for meeting-complete states when delivery is not generated yet.
- [ ] Keep `Retry Delivery Generation` only for delivery generation failure.
- [ ] Keep `Reopen Brief` unavailable unless the meeting failed before a usable meeting result exists.
- [ ] Run `npm run build` from `web`.

### Task 5: Backend and Full-Flow Verification

**Files:**
- No new files required.

- [ ] Run backend regression tests: `uv run pytest tests/test_workflow_repositories.py tests/test_clarification_routes.py tests/test_meeting_graph.py tests/test_clarification_schemas.py -q`.
- [ ] Run frontend build: `npm run build` from `web`.
- [ ] Check `git status --short` in the feature worktree.
- [ ] Commit implementation.
