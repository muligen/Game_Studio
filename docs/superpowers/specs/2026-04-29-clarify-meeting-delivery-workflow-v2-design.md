# Clarify Meeting Delivery Workflow V2 Design

Date: 2026-04-29

## Purpose

Redesign the product iteration workflow as one coherent flow:

```text
Clarify Brief -> Kickoff Meeting -> Delivery
```

The current UI still mixes responsibilities across clarification, meeting, and delivery surfaces. This makes it possible for users to see actions from different phases at the same time, such as returning to clarification while a kickoff has already started. The V2 design establishes a single workflow phase model that drives all card actions, dialogs, and progress displays.

## Product Principles

- The user should always see one current phase and one primary next action.
- Clarification is only for creating or editing the brief.
- Meeting is only for kickoff execution, transcript, minutes, and meeting-to-delivery handoff.
- Delivery is only for executing generated work.
- No component should independently invent its own phase rules.
- Once a meeting is queued or running, the UI must not automatically return to clarification.

## Workflow Phases

The frontend should derive one phase per active requirement:

```ts
type RequirementWorkflowPhase =
  | 'no_brief'
  | 'clarifying'
  | 'brief_ready'
  | 'meeting_queued'
  | 'meeting_running'
  | 'meeting_failed'
  | 'meeting_complete'
  | 'delivery_generating'
  | 'delivery_failed'
  | 'delivery_ready'
  | 'delivery_active'
```

Allowed forward transitions:

```text
no_brief -> clarifying
clarifying -> brief_ready
brief_ready -> meeting_queued
meeting_queued -> meeting_running
meeting_running -> meeting_complete
meeting_running -> meeting_failed
meeting_complete -> delivery_generating
delivery_generating -> delivery_ready
delivery_generating -> delivery_failed
delivery_ready -> delivery_active
```

Explicit recovery transitions:

```text
meeting_failed -> meeting_queued
meeting_failed -> clarifying
delivery_failed -> delivery_generating
```

The `meeting_failed -> clarifying` transition is only allowed when the user explicitly chooses `Reopen Brief`.

## Phase Derivation

Create a single frontend derivation function:

```ts
deriveRequirementWorkflowState(input): RequirementWorkflowState
```

Inputs:

- `requirement`
- `clarificationSession`
- `kickoffTask`
- `deliverySummary`

Output:

```ts
interface RequirementWorkflowState {
  phase: RequirementWorkflowPhase
  phaseLabel: string
  primaryAction: WorkflowAction
  secondaryActions: WorkflowAction[]
  progressSteps: WorkflowProgressStep[]
  canOpenClarify: boolean
  canOpenMeeting: boolean
  canOpenDelivery: boolean
}
```

This function is the only place that decides which actions are available. UI components render the result instead of checking raw statuses directly.

## Phase Rules

### Clarify-Eligible Phases

The UI may open clarification only in:

```text
no_brief
clarifying
brief_ready
meeting_failed after explicit Reopen Brief
```

### Meeting-Eligible Phases

The UI may open meeting detail in:

```text
meeting_queued
meeting_running
meeting_failed
meeting_complete
delivery_generating
delivery_failed
delivery_ready
```

### Delivery-Eligible Phases

The UI may open delivery in:

```text
delivery_ready
delivery_active
```

## Timeline Card

The requirements timeline is the workflow control surface. Each active iteration card shows:

- Requirement title and kind.
- Derived phase label.
- Compact three-stage progress:

```text
Clarify -> Meeting -> Delivery
```

- If meeting is active, a compact meeting node graph:

```text
Prepare -> Opinions -> Summary -> Discussion -> Minutes -> Delivery Plan
```

- One primary action.
- Optional secondary actions.

Primary action table:

```text
no_brief: Start Clarifying
clarifying: Continue Clarifying
brief_ready: Start Meeting
meeting_queued: View Meeting
meeting_running: View Meeting
meeting_failed: Retry Meeting
meeting_complete: Generate Delivery
delivery_generating: View Meeting
delivery_failed: Retry Delivery Generation
delivery_ready: Open Delivery
delivery_active: Open Delivery
```

Secondary action table:

```text
brief_ready: Edit Brief
meeting_failed: View Meeting, Reopen Brief
meeting_complete: View Meeting, View Minutes
delivery_failed: View Meeting, View Minutes
delivery_ready: View Meeting
delivery_active: View Meeting
```

## Clarify Surface

The clarification dialog or page only handles brief creation and editing.

Responsibilities:

- Run the requirement clarifier chat.
- Show current brief fields and readiness.
- Allow editing while no meeting is active.
- Start meeting when the brief is ready.

It must not show:

- Running meeting state.
- Meeting transcript/minutes.
- Delivery plan generation.
- Delivery board links, except after closing and returning to the timeline.

When `Start Meeting` succeeds, the clarify surface closes and the meeting detail opens.

## Meeting Detail Surface

Meeting detail is the owner of kickoff execution and delivery generation handoff.

Responsibilities:

- Show full meeting graph.
- Show active node and active agent.
- Show elapsed time.
- Show transcript and minutes actions.
- Handle meeting retry after failure.
- Handle delivery generation after meeting completion.
- Handle delivery generation retry after failure.

Actions by phase:

```text
meeting_queued: View status
meeting_running: View Transcript when available
meeting_failed: Retry Meeting, Reopen Brief
meeting_complete: Generate Delivery, View Minutes, View Transcript
delivery_generating: View progress, View Minutes
delivery_failed: Retry Delivery Generation, View Minutes, View Transcript
delivery_ready: Open Delivery, View Minutes, View Transcript
```

`Reopen Brief` must communicate that the failed meeting attempt will be superseded by the edited brief. It is unavailable during queued/running/completed meeting phases.

## Delivery Surface

Delivery remains the execution board. It receives the user only after generated delivery data exists.

Responsibilities:

- Show generated plans, tasks, decision gates, and task status.
- Continue execution workflow.
- Avoid sending users back to clarification.

If delivery generation fails, recovery happens in meeting detail, not delivery board.

## Backend/API Needs

Existing kickoff task progress fields are useful and should remain:

- `status`
- `current_node`
- `completed_nodes`
- `active_agents`
- `progress_events`
- `meeting_result`
- `error`
- `started_at`
- `updated_at`

The frontend also needs read-only session lookup:

```http
GET /api/clarifications/requirements/{req_id}/session
```

This endpoint must not create a session or transition requirement state. It only returns the existing session or `null`.

Future improvement, not required for the first V2 implementation:

```http
GET /api/requirements/{req_id}/workflow-state
```

That endpoint could centralize phase derivation on the backend if the frontend derivation becomes too complex.

## Error Handling

Meeting failure:

- Timeline shows `Meeting Failed`.
- Primary action is `Retry Meeting`.
- Secondary actions are `View Meeting` and `Reopen Brief`.
- Clarification does not open automatically.

Delivery generation failure:

- Timeline shows `Delivery Generation Failed`.
- Primary action is `Retry Delivery Generation`.
- Secondary actions are `View Meeting` and `View Minutes`.
- Clarification is unavailable.

Server restart during meeting:

- Existing recovery can mark running kickoff tasks failed.
- UI treats this as `meeting_failed`.
- User may retry meeting or reopen brief.

## Implementation Plan

1. Create workflow derivation types and tests.
2. Update timeline card to render derived workflow state.
3. Simplify clarification surface so it owns only brief work.
4. Create/refine meeting detail surface as kickoff and delivery-generation owner.
5. Wire actions through the derived workflow state.
6. Verify full flow:

```text
Create requirement
-> Clarify brief
-> Start meeting
-> Watch meeting graph
-> Generate delivery
-> Open delivery board
```

## Testing Strategy

Unit tests:

- `deriveRequirementWorkflowState` for all phases.
- Action availability for each phase.
- Clarification cannot open from meeting-running phases.

Backend tests:

- Read-only clarification session endpoint does not create session.
- Kickoff task progress still records meeting nodes.
- Repository save retry still protects Windows task writes.

Frontend build:

- `npm run build` from `web`.

Targeted manual test:

- Start from a fresh requirement.
- Clarify until ready.
- Start meeting.
- Confirm timeline switches to `View Meeting`.
- Confirm clarification does not reopen during meeting.
- Confirm meeting detail shows graph progress.
- Confirm completed meeting can generate/open delivery.

## Out Of Scope

- Redesigning delivery task execution cards.
- Replacing the existing LangGraph meeting topology.
- Moving all workflow derivation to backend in the first V2 pass.
- Starting frontend dev server automatically.
