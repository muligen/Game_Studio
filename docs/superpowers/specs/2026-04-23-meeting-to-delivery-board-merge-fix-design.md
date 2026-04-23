# Meeting To Delivery Board Merge Fix Design

## Summary

`feature/meeting-to-delivery-board` already adds the main scaffolding for delivery plans, delivery tasks, decision gates, session leases, API routes, and a web delivery board. Before merging it into `main`, the branch must be tightened so the feature matches the current product and multi-agent architecture.

This spec is intentionally narrow. It does not redesign the whole delivery system. It defines the fixes required to make the existing branch safe to merge and possible to validate from the product flow.

## Current Problems

The branch has four merge blockers:

- The delivery-plan API requires the caller to send `planner_output`, so the frontend or caller effectively becomes the planner.
- Tasks can be created as actionable while a kickoff decision gate is still unresolved.
- The delivery board starts work with a hardcoded `session-placeholder`, not the real project-scoped agent session.
- `DeliveryPlannerAgent` catches Claude errors and returns an empty fallback plan, even though agent configuration is supposed to be strict.

There are also normal merge conflicts because the branch predates the clarification dialog and single-product workbench changes on `main`.

## Goals

- Generate delivery plans on the backend from a completed meeting.
- Use `delivery_planner` agent for plan generation.
- Load meeting, requirement, design, and user decision context before planning.
- Treat unresolved kickoff conflicts as a one-time decision gate before development.
- Prevent any delivery task from starting before the gate is resolved.
- Resume the project-scoped Claude session for the assigned `project_id + owner_agent`.
- Fail clearly when required agent configuration, Claude output, or project session data is missing.
- Keep the delivery board usable for branch validation without forcing the full single-product workbench redesign into this merge.

## Non-Goals

- Do not build multi-product support.
- Do not replace the single-product workbench frontend spec.
- Do not create a full project-management system.
- Do not auto-implement tasks immediately after a meeting.
- Do not introduce fallback delivery plans.
- Do not duplicate full Claude conversation history into local state.

## Required Behavior

### 1. Backend Owns Plan Generation

The API must not accept arbitrary `planner_output` from the frontend.

The endpoint should accept only the identifiers needed to generate the plan, such as:

```json
{
  "project_id": "project_default"
}
```

Given `meeting_id` and `project_id`, the backend loads:

- completed `MeetingMinutes`
- linked requirement
- available clarified requirement/design context
- pending user decision candidates from the meeting
- project-scoped agent session metadata

Then the backend calls `DeliveryPlannerAgent` or an equivalent service wrapper around the `delivery_planner` Claude role. The returned payload becomes the only source for `DeliveryPlan`, `DeliveryTask`, and `KickoffDecisionGate` creation.

If a plan already exists for the meeting, the endpoint may return the existing plan instead of regenerating it.

### 2. Strict Agent Execution

`delivery_planner` must follow the same strict behavior the rest of the agent-management design expects:

- missing profile config is an error
- invalid Claude output is an error
- Claude SDK failure is an error
- empty or malformed task output is an error
- no fallback plan is created

The API should surface these as clear 4xx or 5xx responses with a useful error message. The system should not silently create an empty plan or mark the meeting as planned.

### 3. Decision Gate Blocks Delivery

If the meeting contains unresolved conflicts that require user direction, the generated plan enters:

```text
awaiting_user_decision
```

Before the gate is resolved:

- delivery tasks may be visible only as preview or blocked items
- no task can be started
- no agent session lease can be acquired for implementation
- the board must show the user decision gate as the next action

After the user resolves the gate:

- the selected options are saved on the gate
- the plan is activated
- every actionable task receives the current `decision_resolution_version`
- no stale pre-resolution task can be started
- there should be no further user pending decision during normal development

Implementation detail:

If the branch keeps pre-generated preview tasks, resolving the gate must promote them only after stamping `decision_resolution_version`. If the branch chooses to regenerate tasks after resolution, it must delete or supersede preview tasks so stale tasks are not actionable.

### 4. Task Start Uses Real Project Agent Session

The frontend must not send `session-placeholder`.

Task start should be driven by backend lookup:

```text
task.project_id + task.owner_agent -> ProjectAgentSession
```

The request can be as small as:

```json
{}
```

The backend validates:

- the task is ready
- the plan is active
- the decision gate is resolved if one exists
- all dependency tasks are done
- a project session exists for `project_id + owner_agent`
- the session lease is available
- the task decision version matches the plan decision version

If no session exists, starting the task fails. The system must not create an ad hoc session at task-start time, because that would lose the meeting context.

### 5. Dependency Semantics Stay Explicit

Delivery tasks remain a DAG.

The backend must reject cycles and unknown dependencies. A task is ready only when:

- its plan is active
- its decision version is valid
- every dependency is done
- its owner agent has an available session lease

Blocked tasks should remain visible on the board with a clear blocked reason.

### 6. Frontend Merge Scope

For this merge, the frontend may keep a standalone delivery board route for validation, but it must not fight the single-product workbench direction.

Acceptable for this merge:

- a delivery board page that lists decision gates and delivery tasks
- a user action to resolve the kickoff decision gate
- a user action to start a ready task
- clear blocked/preview/ready/in-progress/done states

Not acceptable for this merge:

- hardcoded session ids
- a UI that asks the user to paste planner output
- tasks shown as startable while a gate is unresolved
- new product-switching or multi-product concepts

The later single-product workbench frontend can embed the same delivery data into lifecycle columns:

```text
Decision Needed -> Ready for Delivery -> In Progress -> Review / Acceptance -> Done
```

## API Shape

### Generate Delivery Plan

```http
POST /meetings/{meeting_id}/delivery-plan?workspace=...
```

Request:

```json
{
  "project_id": "project_default"
}
```

Behavior:

- load completed meeting
- call delivery planner
- persist plan, tasks, and optional decision gate
- return the persisted board data

### Resolve Decision Gate

```http
POST /decision-gates/{gate_id}/resolve?workspace=...
```

Request:

```json
{
  "resolutions": {
    "scope_direction": "ship_mvp_without_elemental_counters"
  }
}
```

Behavior:

- validate every gate item has a selected valid option
- save resolutions
- activate or regenerate the delivery plan
- stamp task decision versions
- broadcast board updates

### Start Delivery Task

```http
POST /delivery-tasks/{task_id}/start?workspace=...
```

Request:

```json
{}
```

Behavior:

- validate task readiness
- look up the project agent session
- acquire the session lease
- mark the task `in_progress`
- return the updated task

## Data Rules

### DeliveryPlan

Required state:

- `status`: `awaiting_user_decision`, `active`, `in_progress`, `completed`
- `decision_gate_id`: optional
- `decision_resolution_version`: required after gate resolution if a gate exists

### DeliveryTask

Required state:

- `status`: `preview`, `blocked`, `ready`, `in_progress`, `review`, `done`
- `owner_agent`: registered agent id
- `depends_on_task_ids`: explicit task ids
- `decision_resolution_version`: required before start when the plan has a gate

### KickoffDecisionGate

Required state:

- `status`: `pending` or `resolved`
- `items`: user-facing conflict decisions
- `resolution_version`: increments on resolution

## Validation And Errors

The branch should add or update tests for these cases:

- Generate plan rejects incomplete meetings.
- Generate plan invokes `delivery_planner` instead of accepting caller-supplied planner output.
- Claude planner failure does not create fallback tasks.
- Unknown owner agent is rejected.
- Dependency cycles are rejected.
- Unresolved gate blocks task start.
- Gate resolution stamps task decision versions.
- Stale or missing task decision version blocks task start.
- Task start fails when the project agent session is missing.
- Task start does not require a frontend-provided session id.
- Frontend start action does not send `session-placeholder`.

## Merge Conflict Resolution Notes

When merging into current `main`, preserve both sides of these existing changes:

- `studio/api/main.py`: include clarification routes and delivery routes.
- `studio/llm/__init__.py`: include clarification-related exports and delivery planner exports.
- `studio/llm/claude_roles.py`: preserve current JSON compatibility/logging behavior and add delivery planner role support.
- `studio/storage/workspace.py`: preserve clarification/session repositories and add delivery repositories.
- `tests/test_agent_profiles.py`: include clarification agents and delivery planner expectations.
- `tests/test_claude_roles.py`: keep current strict parsing tests and add delivery planner role coverage.
- `web/src/lib/api.ts`: preserve clarification API/types and add delivery API/types.

## Acceptance Criteria

- A completed meeting can generate a delivery plan without manually passing `planner_output`.
- If the meeting has conflicts, the board shows a decision gate and no task can start.
- After resolving the decision gate, ready tasks become startable with a valid decision version.
- Starting a task uses the stored project agent session for its owner agent.
- Starting a task fails clearly if the required project agent session does not exist.
- No delivery planner fallback creates empty tasks.
- The delivery branch merges with current `main` without losing clarification dialog or single-product workbench code.
- Targeted backend tests pass.
- Frontend build passes.

## Recommended Implementation Order

1. Update backend tests to express strict planner generation and gate blocking.
2. Replace caller-supplied `planner_output` with backend planner invocation.
3. Remove delivery planner fallback.
4. Fix gate preview/promotion/version semantics.
5. Change task start to resolve sessions server-side.
6. Remove frontend `session-placeholder` and planner-output assumptions.
7. Resolve merge conflicts against `main`.
8. Run targeted backend tests and frontend build.

