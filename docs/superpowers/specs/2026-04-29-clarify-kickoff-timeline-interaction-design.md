# Clarify Kickoff Timeline Interaction Design

Date: 2026-04-29

## Purpose

Redesign the requirement clarification and kickoff interaction so users always know where the iteration is in the product workflow, and so a running kickoff meeting cannot accidentally appear to return to the clarification phase.

The current confusing behavior comes from using the clarification dialog as both the clarification surface and the kickoff status surface. After kickoff starts, the UI can still feel like it belongs to the clarify phase, especially around failure and retry actions.

## Goals

- Make the iteration timeline the primary workflow entry point.
- Show kickoff meeting progress directly on the requirement card.
- Move running and completed kickoff details into a dedicated meeting detail surface.
- Prevent automatic or ambiguous jumps back to clarification after kickoff starts.
- Keep retry and edit actions explicit when kickoff fails.

## State Model

The UI should present a single user-facing phase for each active iteration:

```text
clarifying
ready_for_kickoff
kickoff_running
kickoff_failed
kickoff_complete
delivery_ready
```

Allowed transitions:

```text
clarifying -> ready_for_kickoff
ready_for_kickoff -> kickoff_running
kickoff_running -> kickoff_complete
kickoff_running -> kickoff_failed
kickoff_complete -> delivery_ready
kickoff_failed -> kickoff_running
kickoff_failed -> clarifying
```

The `kickoff_failed -> clarifying` transition is only allowed when the user explicitly chooses `Edit Clarification`.

## Timeline Card Behavior

Each active requirement card should show the current phase and the next safe action.

```text
Clarifying
Action: Continue Clarifying

Ready For Kickoff
Action: Start Kickoff

Kickoff Running
Action: View Meeting

Kickoff Failed
Actions: Retry Kickoff, Edit Clarification

Kickoff Complete / Delivery Ready
Actions: View Delivery, View Meeting
```

When kickoff is running or failed, the timeline card should show a compact meeting graph:

```text
Prepare -> Opinions -> Summary -> Discussion -> Minutes -> Delivery Plan
```

Step display rules:

- Completed steps show done.
- Current step shows active.
- Future steps show pending.
- `Discussion` is optional and shows skipped if the meeting reaches minutes without a discussion step.
- Failed kickoff highlights the current or last known failed step.

## Detail Surfaces

### Clarification Dialog

This dialog is only for collecting and editing the meeting brief.

It is reachable from:

- `clarifying`
- `ready_for_kickoff`
- `kickoff_failed`, but only through explicit `Edit Clarification`

It is not reachable from:

- `kickoff_running`
- `kickoff_complete`
- `delivery_ready`

### Kickoff Detail Dialog

Running and completed kickoff states should open a dedicated `KickoffDetailDialog`, not the clarification dialog.

It contains:

- Full meeting graph.
- Current node and active agent.
- Elapsed time.
- Meeting transcript action.
- Meeting minutes action when available.
- Delivery board action when delivery is ready.
- Failure actions when kickoff fails.

Failure actions:

- `Retry Kickoff`: starts a new kickoff attempt using the current brief.
- `Edit Clarification`: reopens the brief after warning that the failed kickoff attempt will be superseded.

## Guardrails

The UI should enforce these rules:

- `Start Kickoff` appears only in `ready_for_kickoff`.
- `View Meeting` replaces `Start Kickoff` once kickoff starts.
- `Edit Clarification` never appears during `kickoff_running`.
- A running kickoff cannot close and reopen into the clarification chat automatically.
- Reopening the page should reconstruct the same phase from persisted kickoff task/session state.

The backend should continue returning enough kickoff task state for the timeline card and detail dialog:

- `status`
- `current_node`
- `completed_nodes`
- `active_agents`
- `progress_events`
- `meeting_result`
- `error`

## Error Handling

If kickoff fails before a meeting result exists:

- Timeline card shows `Kickoff Failed`.
- Detail dialog shows the failed step if known.
- Actions are `Retry Kickoff` and `Edit Clarification`.

If kickoff succeeds but delivery plan generation fails:

- The meeting graph remains complete through `Minutes`.
- `Delivery Plan` step shows failed.
- Actions are `Retry Generate Delivery Plan`, `View Transcript`, and `View Minutes`.
- The UI should not send the user back to clarification automatically.

## Testing

Backend tests:

- Kickoff task API returns progress fields.
- Meeting graph records completed/current nodes.
- Delivery plan failure is represented separately from meeting failure.

Frontend checks:

- Timeline card action is `View Meeting` during kickoff running.
- `Start Kickoff` is hidden after kickoff starts.
- Clarification dialog is not opened from `kickoff_running`.
- Kickoff detail dialog shows compact/full graph states.
- `Edit Clarification` appears only on kickoff failure.

## Out Of Scope

- Full redesign of the delivery board.
- Changing the underlying meeting graph node order.
- Replacing transcript or minutes storage.
- Starting frontend dev server automatically during implementation.
