# Real Web E2E: Kickoff To Delivery

## Goal

Provide a real end-to-end browser test that replaces manual web clicking for the main product flow:

1. Create an MVP requirement in the web UI
2. Clarify it through the real clarification dialog
3. Start a real kickoff meeting
4. Verify meeting transcript artifacts exist
5. Verify delivery artifacts appear on the delivery board

This test is intended for operator-driven verification. The user starts the backend and frontend manually. Playwright then drives the browser and performs UI plus API assertions.

## Non-Goals

- Do not mock Claude, kickoff, transcript generation, or delivery planning
- Do not cover every board workflow in the first version
- Do not validate filesystem artifacts directly in the first version
- Do not automate server startup or teardown

## Why This Shape

Pure UI smoke tests are not enough for this product because success on the page can still hide missing meeting or delivery artifacts.

Direct filesystem assertions are too coupled to workspace layout and create brittle tests.

So the first version should use:

- real browser interactions
- real backend APIs
- real Claude-backed meeting and delivery flow
- API-based artifact verification after UI actions

## User Flow Under Test

The test will run this exact path:

1. Open the Requirements Board
2. Create a new MVP requirement with a unique title
3. Open `Clarify MVP`
4. Send a real clarification message
5. Wait until kickoff becomes available
6. Start kickoff
7. Wait for kickoff completion UI
8. Open the transcript viewer and confirm structured discussion entries exist
9. Open the Delivery Board
10. Confirm that the board contains at least one generated artifact:
   - an open kickoff decision gate, or
   - preview tasks, or
   - ready tasks

## Test Strategy

### One Primary Spec

The first version should have one primary Playwright spec covering the main happy path.

This is enough to replace the most common manual acceptance loop without creating a large flaky suite.

### Dual Assertions

Each major stage should be asserted twice when possible:

- UI assertion: what the user can see
- API assertion: what the system actually produced

This is the core design principle of the test.

### Real Data Isolation

The spec should create a unique requirement title per run so repeated executions do not collide with old manual data.

Recommended pattern:

- `PW E2E Snake MVP <timestamp>`

The test should capture the resulting `meeting_id` and `project_id` from the kickoff result UI or linked API data for downstream assertions and debug output.

## Required Assertions

### Clarification

The test should verify:

- the clarification dialog opens
- the user message is accepted
- the assistant replies
- kickoff becomes available

The test does not need to prove the full semantic quality of clarification output. It only needs to prove that the real flow advances to kickoff readiness.

### Kickoff

The test should verify:

- the kickoff phase transitions out of idle
- kickoff completion UI is shown
- `Project ID` is visible
- `Meeting ID` is visible
- transcript entry point is visible

### Transcript

The test should verify both:

- transcript dialog opens in the UI
- transcript API returns non-empty `events`

At least one event should come from `moderator`, and at least one event should come from a non-moderator agent.

### Delivery

The test should verify both:

- the delivery board page opens
- the delivery board API returns generated artifacts for the current workspace

Accepted artifact outcomes:

- one or more open decision gates
- one or more `preview` tasks
- one or more `ready` tasks

The first version should not require tasks to reach `in_progress` or `done`.

## Test Environment

The user starts services manually before running Playwright:

- frontend dev server
- backend API server

The Playwright suite should read these values from environment variables:

- `E2E_BASE_URL`
- `E2E_API_URL`
- `E2E_WORKSPACE`

Suggested defaults:

- `E2E_BASE_URL=http://127.0.0.1:5173`
- `E2E_API_URL=http://127.0.0.1:8000`
- `E2E_WORKSPACE=.`

## Timeouts And Reliability

Kickoff and delivery planning are real and can be slow.

The spec should therefore:

- use a long per-test timeout
- use generous waits around kickoff completion
- prefer polling for visible state transitions over fixed sleeps

The suite should fail with useful context rather than fail fast with no state captured.

## Failure Diagnostics

On failure, the test should capture:

- screenshot
- page HTML
- Playwright trace
- the generated requirement title
- any discovered `meeting_id`
- any discovered `project_id`

This is required because real Claude-backed failures are often intermittent and need artifact-based diagnosis.

## Proposed File Layout

```text
web/
  e2e/
    kickoff-to-delivery.spec.ts
    helpers/
      api.ts
      selectors.ts
  playwright.config.ts
```

## Implementation Notes

### Browser Actions

The test should only use user-visible interactions:

- click buttons
- fill dialogs
- navigate through existing UI

It should not seed requirements through the backend API, because the point is to replace manual browser acceptance.

### API Helpers

Helper functions may call backend APIs for verification only. They should not create or mutate the main happy-path state except when retrieving transcript or board state.

### Workspace Scope

The first version should assume a single active workspace and read it from `E2E_WORKSPACE`.

## Acceptance Criteria

The work is complete when:

1. Playwright can be run against manually started services
2. The browser test creates a real requirement through the UI
3. The browser test completes a real clarify-to-kickoff flow
4. The test proves transcript events were generated
5. The test proves delivery artifacts were generated
6. Failures produce enough artifacts to debug without rerunning immediately

## Out Of Scope Follow-Ups

- auto-start backend/frontend from Playwright
- multiple scenario coverage
- filesystem artifact assertions
- automatic resolution of kickoff decision gates
- agent execution after task creation
