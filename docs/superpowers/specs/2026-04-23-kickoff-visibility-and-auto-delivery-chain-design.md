# Kickoff Visibility And Auto Delivery Chain Design

## Goal

Make kickoff feel like a visible product workflow instead of a hidden backend action:

1. Users can clearly tell when kickoff has started, whether it is still running, and where to view its result.
2. After kickoff completes, the system automatically generates the delivery plan and shows the resulting board state without requiring manual API calls.

## Problem

The current flow is technically functional but fragmented:

- `Start Kickoff Meeting` runs the meeting graph synchronously and then closes the clarification dialog.
- Users do not get a strong confirmation that the meeting actually ran.
- Meeting output exists in storage and APIs, but there is no clear product-level result view.
- Delivery planning exists as a separate capability, but kickoff does not automatically trigger it.
- From a user perspective, the chain breaks between "start meeting" and "see tasks on the board."

This creates uncertainty:

- "Did the meeting really start?"
- "Where do I see the meeting result?"
- "Why didn't tasks appear after the meeting?"

## Scope

This spec only covers the post-clarification kickoff experience.

In scope:

- visible kickoff progress state in the frontend
- visible kickoff result summary and result entry points
- automatic delivery plan generation after kickoff
- automatic navigation to the delivery board after the chain succeeds
- clear handling when kickoff completes but a kickoff decision gate is created

Out of scope:

- real-time per-node LangGraph visualization in the web app
- redesigning meeting prompts or participant logic
- redesigning the delivery board itself
- changing delivery execution semantics

## User Experience

### Intended Flow

1. User finishes clarification and clicks `Start Kickoff Meeting`.
2. The clarification dialog switches into a kickoff-running state instead of closing immediately.
3. The UI shows that kickoff is in progress.
4. When kickoff completes, the frontend immediately requests delivery plan generation.
5. If delivery plan generation succeeds:
   - the user sees a short kickoff result summary
   - the UI navigates to the Delivery Board
6. The Delivery Board shows:
   - generated tasks if there is no unresolved decision gate
   - or an open kickoff decision gate plus preview tasks if user input is still required

### User-Facing States

- `clarifying`: normal chat and context preview
- `kickoff_running`: kickoff request has been sent and the meeting graph is running
- `kickoff_completed`: meeting finished and produced a `meeting_id`
- `delivery_generating`: delivery planner is generating board items
- `delivery_ready`: navigation target is ready
- `kickoff_failed`: kickoff failed
- `delivery_failed`: kickoff succeeded but delivery plan generation failed

## Product Decisions

### 1. Kickoff Should Not Feel Invisible

After the user clicks kickoff, the current dialog should remain open and switch to a progress/result mode.

Minimum information shown while running:

- requirement title
- current phase label: `Starting kickoff meeting...`
- lightweight explanation: `The system is running the kickoff meeting and will generate delivery tasks when it finishes.`

Minimum information shown after kickoff success:

- `project_id`
- `meeting_id`
- meeting result summary if available
- buttons:
  - `Open Delivery Board`
  - `View Meeting Minutes` (if meeting result is already available)

### 2. Delivery Generation Must Be Automatic

The frontend should automatically call delivery plan generation using the `meeting_id` and `project_id` returned by kickoff.

Users should not need to:

- inspect network responses
- manually call `/meetings/{meeting_id}/delivery-plan`
- manually infer that a second step is required

### 3. Meeting Results Should Be Discoverable

The system should expose a simple result view for kickoff output.

Minimum result data to show in the frontend:

- meeting summary
- attendees
- consensus points
- conflict points
- whether unresolved decisions remain

This can initially be shown inside the clarification dialog success state or a lightweight dedicated result panel. It does not need a full new page in the first iteration.

### 4. Decision Gates Remain the Correct Blocker

If kickoff identifies unresolved conflicts and the delivery planner creates a decision gate:

- delivery generation is still considered successful
- the user is taken to the Delivery Board
- the board shows the open gate and preview tasks
- development remains blocked until the gate is resolved

This preserves the current delivery semantics while improving user clarity.

## Backend Changes

### Kickoff API

Current endpoint:

- `POST /api/clarifications/requirements/{req_id}/kickoff`

Keep the kickoff API synchronous for now. Do not introduce background job orchestration in this iteration.

Required behavior:

- continue returning `project_id`, `requirement_id`, `meeting_id`, and kickoff status
- additionally return a compact meeting result snapshot when available

Suggested response shape:

```json
{
  "project_id": "proj_xxx",
  "requirement_id": "req_xxx",
  "meeting_id": "meeting_xxx",
  "status": "kickoff_complete",
  "meeting": {
    "id": "meeting_xxx",
    "title": "Kickoff for turn-based combat MVP",
    "summary": "The team agreed on a small combat MVP with one playable loop.",
    "attendees": ["design", "dev", "qa"],
    "consensus_points": ["Start with one battle loop"],
    "conflict_points": ["Progression depth is deferred"],
    "pending_user_decisions": []
  }
}
```

This avoids forcing the frontend to make an immediate extra read just to show the result.

### Delivery Generation API

No contract change required for the existing delivery generation endpoint.

Existing endpoint:

- `POST /api/meetings/{meeting_id}/delivery-plan`

The frontend will call this automatically after kickoff success.

## Frontend Changes

### Requirement Clarification Dialog

Modify `RequirementClarificationDialog` to own a small kickoff workflow state machine.

Add local state for:

- kickoff run status
- kickoff result payload
- delivery generation status
- delivery generation result summary

Behavior changes:

- clicking `Start Kickoff Meeting` no longer closes the dialog immediately
- while kickoff is pending, disable chat input and kickoff button
- on kickoff success, store returned `meeting_id`, `project_id`, and meeting snapshot
- immediately call `deliveryApi.generatePlan(...)`
- on delivery generation success:
  - show success state briefly or immediately navigate to `/delivery`
  - pass along context if needed through query params or shared board filters
- on delivery generation failure:
  - keep the dialog open
  - show kickoff success and delivery failure separately
  - give the user a retry action for delivery generation

### Delivery Board Entry

The frontend should navigate to the Delivery Board automatically after delivery plan generation succeeds.

Preferred first iteration:

- navigate to `/delivery`
- optionally include `requirement_id` in routing state or query params to support future filtering

### Meeting Result View

Do not build a full standalone page in this iteration.

Use a compact dialog state that shows:

- kickoff complete
- meeting summary
- key consensus/conflict bullets
- buttons for:
  - `Open Delivery Board`
  - `View Meeting Minutes`

`View Meeting Minutes` can initially open a lightweight detail section or a future route. The main requirement is discoverability, not full polish.

## Error Handling

### Kickoff Failure

If kickoff fails:

- stay in the dialog
- show a dedicated kickoff failure message
- do not attempt delivery generation

### Delivery Generation Failure

If kickoff succeeds but delivery generation fails:

- preserve the kickoff result in UI
- show that meeting output exists
- show that delivery generation failed separately
- offer:
  - `Retry Generate Delivery Plan`
  - `View Meeting Minutes`

This distinction matters because a successful kickoff already produced valuable output.

## Data Flow

### Success Path

1. User clicks kickoff in `RequirementClarificationDialog`
2. Frontend calls clarification kickoff API
3. Backend runs meeting graph and persists meeting minutes
4. Backend returns kickoff payload including `meeting_id`, `project_id`, and meeting snapshot
5. Frontend stores kickoff result and enters `delivery_generating`
6. Frontend calls delivery generation API
7. Backend persists delivery plan, tasks, and optional decision gate
8. Frontend navigates to Delivery Board

### Partial Failure Path

1. Kickoff succeeds
2. Meeting minutes exist
3. Delivery generation fails
4. Frontend remains on result state and offers retry

## Files Likely To Change

Backend:

- `studio/api/routes/clarifications.py`

Frontend:

- `web/src/components/common/RequirementClarificationDialog.tsx`
- `web/src/lib/api.ts`
- optionally `web/src/pages/DeliveryBoard.tsx` if route/query handling is added

Tests:

- `tests/test_clarification_routes.py`
- frontend tests if present for clarification dialog behavior

## Acceptance Criteria

1. After clicking `Start Kickoff Meeting`, the user sees a clear in-progress state instead of the dialog closing immediately.
2. When kickoff succeeds, the frontend has direct access to `meeting_id`, `project_id`, and a compact meeting result snapshot.
3. The frontend automatically triggers delivery plan generation after kickoff success.
4. If delivery generation succeeds, the user is taken to the Delivery Board without manual API work.
5. If a kickoff decision gate exists, the Delivery Board shows it and tasks remain blocked/preview as designed.
6. If kickoff succeeds but delivery generation fails, the user can still see that kickoff completed and can retry delivery generation.
7. The user has a clear way to inspect kickoff result output without digging into `.studio-data` or browser network logs.

## Rollout Notes

This is intentionally a minimal productization pass over the existing backend flow.

It does not require:

- background jobs
- websocket-driven meeting progress
- a full meeting details page

Those can be added later if kickoff runtime and visibility requirements grow.
