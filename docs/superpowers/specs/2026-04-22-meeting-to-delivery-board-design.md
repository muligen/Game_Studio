# Meeting To Delivery Board Design

## Summary

After a kickoff meeting completes, Game Studio should turn the meeting minutes into a visible delivery plan on the web board. The plan must preserve task dependencies, surface unresolved user decisions, and ensure implementation agents receive the meeting context before taking work.

This feature connects three currently separate pieces:

- Meeting Graph produces `MeetingMinutes`.
- The board shows workflow items.
- Project agent sessions preserve each agent's Claude context after kickoff.

## Problem

Meeting Graph currently saves meeting minutes only:

```text
workspace.meetings.save(minutes)
```

The minutes contain useful output:

- `decisions`
- `action_items`
- `pending_user_decisions`
- `consensus_points`
- `conflict_points`
- `supplementary`

But nothing turns those outputs into visible implementation work. The original requirement remains `draft`, and the board does not show:

- what tasks should be done next
- which tasks depend on earlier tasks
- which tasks are blocked by user decisions
- which agent should take each task
- whether the implementation agent has inherited the kickoff meeting context

## Goals

- Convert completed meeting minutes into a structured delivery plan.
- Represent task dependencies explicitly.
- Represent pending user decisions as first-class board items.
- Block dependent tasks until required user decisions are resolved.
- Assign tasks to the intended agent role.
- Pass meeting context and meeting decisions to the assigned agent when it starts implementation.
- Make the plan visible from the web board.
- Keep generation bounded and reviewable; do not automatically implement tasks immediately after meeting.

## Non-Goals

- Do not build a full project-management system.
- Do not support arbitrary dynamic agent roles.
- Do not let unresolved conflicts become implementation tasks silently.
- Do not auto-start development immediately after meeting.
- Do not duplicate Claude chat history in LangGraph state.
- Do not replace the existing requirement workflow in this change.

## Direct Answers To The Three Design Questions

### 1. How do we solve task dependencies?

Use a task DAG, not a flat task list.

Each generated delivery task has:

- `id`
- `title`
- `description`
- `owner_agent`
- `depends_on_task_ids`
- `blocked_by_decision_ids`
- `source_meeting_id`
- `source_requirement_id`
- `handoff_context`
- `status`

The backend validates that the dependency graph has no cycles. A task is `ready` only when:

- every task in `depends_on_task_ids` is completed
- every decision in `blocked_by_decision_ids` is resolved

Tasks whose dependencies are unmet stay visible on the board, but they show a blocked reason and cannot be claimed or started.

### 2. How do user decisions appear on the board, and do they block other steps?

User decisions become first-class `DecisionItem` cards on the board.

Each `pending_user_decisions` entry from meeting minutes becomes either:

- a decision card if it requires human choice
- or supporting context attached to an existing decision card if similar

Decision cards have:

- `id`
- `question`
- `context`
- `options`
- `status`: `open`, `resolved`, or `cancelled`
- `resolution`
- `source_meeting_id`
- `source_requirement_id`

Yes, unresolved decisions can block tasks. A task with `blocked_by_decision_ids` cannot move into implementation until those decision cards are resolved.

Not every task must be blocked. Work that is independent of the unresolved choice can proceed. For example:

- "Build deterministic turn-order skeleton" can proceed.
- "Implement skill resource system" is blocked until the user chooses cooldown or resource.
- "Implement elemental counters" is blocked or deferred until the elemental counter decision is resolved.

This keeps useful work moving without pretending undecided scope is approved.

### 3. Are implementation agents the same agents from the meeting, and do they receive the meeting spirit?

They should use the same project-scoped agent session when possible.

Kickoff creates per-agent project sessions. Meeting participants such as `design`, `dev`, and `qa` use those sessions during the meeting. Generated tasks are assigned to agent roles, and execution should look up the same `project_id + agent` session before calling Claude.

Each task also stores a compact `handoff_context` built from the meeting minutes:

- meeting title
- relevant decisions
- relevant consensus points
- relevant conflict points
- relevant pending decisions
- assigned-agent opinion summary if present
- task-specific acceptance notes

When the assigned agent starts work, the prompt includes this handoff context and uses the same project session. This gives two layers of continuity:

- Claude session continuity from kickoff
- explicit task handoff context for auditability and deterministic prompt construction

If no project session exists, task execution must fail clearly. It should not create an ad hoc session or silently run without meeting context.

## Recommended Approach

Add a small delivery-planning layer instead of overloading `MeetingMinutes` or immediately mutating the original `RequirementCard`.

New backend concepts:

- `DeliveryPlan`: one plan generated from one meeting.
- `DeliveryTask`: a task in the plan, with dependencies and owner.
- `DecisionItem`: a user decision gate that can block tasks.

The web board can then show a combined project view:

- requirement cards
- delivery task cards
- decision cards

This avoids squeezing task dependencies and decision gates into the existing `RequirementCard` schema, while still making the result visible on the board.

## Alternatives Considered

### Option 1: Convert action items directly into RequirementCards

Pros:

- Fastest implementation.
- Reuses current board columns.

Cons:

- `RequirementCard` has no dependency fields.
- No first-class decision gate.
- Easy to accidentally send unresolved conflicts into development.
- Blurs parent requirement vs implementation task.

### Option 2: Store only enriched meeting minutes

Pros:

- Minimal backend changes.
- Keeps Meeting Graph output simple.

Cons:

- Board still does not show actionable work.
- User cannot resolve decisions from the board.
- Agents still lack task-level handoff.

### Option 3: Add DeliveryPlan, DeliveryTask, and DecisionItem

Pros:

- Models dependencies correctly.
- Models user decisions as blockers.
- Keeps original requirements intact.
- Supports agent assignment and context handoff.
- Can still be displayed on the existing board.

Cons:

- Requires new schemas, storage, API routes, and frontend card types.

Recommendation: Option 3.

## Data Model

### DeliveryPlan

Stored at:

```text
.studio-data/delivery_plans/<plan_id>.json
```

Example:

```json
{
  "id": "plan_meeting_8fab476c",
  "meeting_id": "meeting_8fab476c",
  "requirement_id": "req_8fab476c",
  "project_id": "proj_123",
  "status": "draft",
  "task_ids": ["task_combat_loop", "task_skill_system"],
  "decision_ids": ["decision_skill_cost"],
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Plan statuses:

- `draft`: generated but not accepted.
- `active`: visible and actionable on the board.
- `completed`: all tasks complete and decisions resolved.
- `cancelled`: user cancelled the plan.

### DeliveryTask

Stored at:

```text
.studio-data/delivery_tasks/<task_id>.json
```

Example:

```json
{
  "id": "task_combat_loop",
  "plan_id": "plan_meeting_8fab476c",
  "meeting_id": "meeting_8fab476c",
  "requirement_id": "req_8fab476c",
  "project_id": "proj_123",
  "title": "Implement deterministic 3v3 combat loop",
  "description": "Build the core loop: fixed speed order, attack, skill, defend, HP win/loss.",
  "owner_agent": "dev",
  "status": "ready",
  "depends_on_task_ids": [],
  "blocked_by_decision_ids": [],
  "acceptance_criteria": [
    "A 3v3 battle can complete with win/loss result.",
    "Turn order follows speed sorting."
  ],
  "handoff_context": {
    "meeting_title": "Turn-Based Combat MVP Kickoff Meeting Minutes",
    "relevant_decisions": ["Core combat loop locked to 3v3 with fixed speed sorting"],
    "relevant_consensus": ["Three action types confirmed: Normal Attack, Skill, Defend"],
    "relevant_conflicts": [],
    "agent_opinion_summary": "Dev recommends MVP with deterministic turn order..."
  },
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Task statuses:

- `blocked`: dependencies or decisions are unresolved.
- `ready`: can be claimed by the owner agent.
- `in_progress`: assigned agent is executing.
- `review`: implementation output is ready for QA/review.
- `done`: completed.
- `cancelled`: removed from scope.

### DecisionItem

Stored at:

```text
.studio-data/decision_items/<decision_id>.json
```

Example:

```json
{
  "id": "decision_skill_cost",
  "plan_id": "plan_meeting_8fab476c",
  "meeting_id": "meeting_8fab476c",
  "requirement_id": "req_8fab476c",
  "project_id": "proj_123",
  "question": "Should MVP skills use cooldowns or a resource cost?",
  "context": "Meeting left skill cost system unresolved. Dev needs this before skill framework implementation.",
  "options": ["cooldown", "resource", "defer skills"],
  "status": "open",
  "resolution": null,
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Decision statuses:

- `open`: waiting for user.
- `resolved`: user chose a resolution.
- `cancelled`: no longer needed.

## Generation Flow

### Trigger

Generation happens after a completed meeting.

Entry points:

- Backend API: `POST /api/meetings/{meeting_id}/delivery-plan`
- Web UI button on a meeting detail panel: `Generate Delivery Plan`
- Future automatic option after kickoff, but not in the first implementation

The first implementation should require explicit user action. This prevents accidental task creation from a meeting with bad or incomplete minutes.

### Planner Agent

Add a profile-backed role:

```text
delivery_planner
```

The planner consumes:

- `MeetingMinutes`
- source `RequirementCard`
- project id if available

It returns strict JSON:

```json
{
  "tasks": [
    {
      "title": "...",
      "description": "...",
      "owner_agent": "dev",
      "depends_on": ["Other task title or temporary key"],
      "blocked_by_decisions": ["Decision temporary key"],
      "acceptance_criteria": ["..."],
      "source_evidence": ["decision/action item text from minutes"]
    }
  ],
  "decisions": [
    {
      "question": "...",
      "context": "...",
      "options": ["..."],
      "source_evidence": ["pending decision text from minutes"]
    }
  ]
}
```

The backend normalizes temporary keys into persisted ids, validates dependencies, and computes initial task status.

### Deterministic Guardrails

The backend must apply these rules after planner output:

- Owner agent must be one of `design`, `dev`, `qa`, `art`, `reviewer`, or `quality`.
- Tasks cannot depend on unknown tasks.
- Tasks cannot be blocked by unknown decisions.
- Dependency graph must be acyclic.
- A task with unresolved decisions starts as `blocked`.
- A task with incomplete task dependencies starts as `blocked`.
- A task with no blockers starts as `ready`.
- Pending user decisions from `MeetingMinutes.pending_user_decisions` must become decision cards or be explicitly attached to an existing decision card.
- `conflict_points` should not become development tasks unless a decision resolved them or the minutes contain a clear decision.

## Board Behavior

Add a board mode or section for delivery planning.

Columns:

- `Decision Needed`: open `DecisionItem` cards.
- `Blocked`: delivery tasks blocked by dependencies or decisions.
- `Ready`: tasks available for the assigned agent.
- `In Progress`: claimed/running tasks.
- `Review`: output ready for QA/review.
- `Done`: completed tasks.

Task cards show:

- title
- owner agent
- source meeting id
- dependency count
- blocking decision count
- acceptance criteria preview

Decision cards show:

- question
- options
- source meeting id
- affected task count
- resolution action

When the user resolves a decision:

- update `DecisionItem.status` to `resolved`
- store `resolution`
- recompute task readiness for tasks blocked by that decision
- broadcast board update

## Blocking Rules

Tasks are blocked if any of these are true:

- `blocked_by_decision_ids` contains an open decision.
- `depends_on_task_ids` contains a task not in `done`.
- required project-agent session is missing.

Blocked tasks remain visible. They cannot be claimed by agents.

Unblocked tasks can proceed even if other independent decisions remain open.

This means user decisions block only the tasks that depend on them, not the entire project by default.

## Agent Execution Handoff

When a task is started by its owner agent:

1. Load `DeliveryTask`.
2. Load source `MeetingMinutes`.
3. Load source `RequirementCard`.
4. Load project-agent session by `project_id + owner_agent`.
5. Build prompt context from:
   - task title and description
   - acceptance criteria
   - dependency outputs if available
   - `handoff_context`
   - full meeting id and source requirement id
6. Invoke the assigned agent using the same project session.
7. Save execution output and update task status.

The execution agent may or may not have attended the kickoff meeting:

- If the owner agent attended, it uses the same project session and gets explicit handoff context.
- If the owner agent did not attend, it still uses the project session if one exists and receives explicit handoff context.
- If no session exists, fail clearly. Do not run without meeting context.

This preserves "meeting spirit" without relying only on implicit chat memory.

## Backend API

### Generate Plan

```http
POST /api/meetings/{meeting_id}/delivery-plan?workspace=<workspace>
```

Response:

```json
{
  "plan": { "...": "DeliveryPlan" },
  "tasks": [],
  "decisions": []
}
```

### List Board Items

```http
GET /api/delivery-board?workspace=<workspace>&requirement_id=<optional>
```

Returns:

```json
{
  "plans": [],
  "tasks": [],
  "decisions": []
}
```

### Resolve Decision

```http
POST /api/decisions/{decision_id}/resolve?workspace=<workspace>
```

Body:

```json
{
  "resolution": "Use cooldowns for MVP skills."
}
```

Response includes updated decision and affected tasks.

### Start Task

```http
POST /api/delivery-tasks/{task_id}/start?workspace=<workspace>
```

Rules:

- task must be `ready`
- owner agent session must exist
- task becomes `in_progress`
- execution can be queued in the existing agent pool

## Frontend Changes

Add or extend board UI:

- Add `Generate Delivery Plan` action on meeting detail.
- Add delivery board columns for decisions and tasks.
- Show blockers directly on cards.
- Add decision resolution dialog.
- Add task detail panel with meeting handoff context.
- Add `Start Agent Work` action only for ready tasks.

The existing Requirements Board should remain available. Delivery board can live as:

- a new route `/delivery`
- or a tab on the requirement detail page

First implementation recommendation: add a new `/delivery` route to avoid overloading the existing requirement columns.

## Error Handling

- Missing meeting: return 404.
- Meeting not completed: reject plan generation.
- Existing plan for meeting: return the existing plan unless explicit regeneration is later added.
- Planner invalid JSON: fail clearly; do not create partial plan.
- Dependency cycle: reject the plan and show planner validation error.
- Unknown owner agent: reject the plan.
- Unresolved decision blocks task start.
- Missing project session blocks task start.
- Agent execution failure moves task back to `ready` or `blocked` with error detail, depending on blocker state.

## Tests

Backend tests:

- Generate delivery plan from completed meeting.
- Reject generation for missing or draft meeting.
- Reject invalid planner output.
- Reject cyclic dependencies.
- Create decision items from all pending user decisions.
- Mark tasks with open decisions as `blocked`.
- Mark independent tasks as `ready`.
- Resolve decision and recompute affected task readiness.
- Start task fails when blocked by decision.
- Start task fails when dependency task is not done.
- Start task uses the owner agent's project session.
- Start task includes meeting handoff context in the agent prompt.

Frontend tests:

- Delivery board lists decision and task cards.
- Blocked task displays blocking decision.
- Decision resolution updates affected task cards.
- Ready task shows `Start Agent Work`.
- Blocked task hides/disables `Start Agent Work`.
- Task detail shows source meeting and handoff context.

Manual acceptance:

- Run a kickoff meeting.
- Generate a delivery plan from the completed meeting.
- Verify decision cards appear for unresolved meeting decisions.
- Verify blocked tasks show why they are blocked.
- Resolve one decision.
- Verify only affected tasks unblock.
- Start a ready dev task.
- Verify the dev agent receives meeting handoff context and project session id.

## Acceptance Criteria

- Completed meeting minutes can be converted into a delivery plan.
- Delivery plan preserves task dependencies as an acyclic graph.
- Pending user decisions appear on the board as decision cards.
- Open decisions block only dependent tasks.
- Independent tasks can proceed while unrelated decisions remain open.
- Task owner agent is explicit and limited to registered agents.
- Task execution uses the project-scoped agent session.
- Task execution prompt includes explicit meeting handoff context.
- The board makes blockers, dependencies, and owner agents visible.
- Existing Meeting Graph, project session, and requirements board behavior remain intact.
