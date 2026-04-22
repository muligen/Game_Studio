# Meeting To Delivery Board Design

## Summary

After a kickoff meeting completes, Game Studio should turn the meeting minutes into a visible delivery plan on the web board. The plan must preserve task dependencies, surface meeting conflicts as a one-time kickoff decision gate, and ensure implementation agents continue from the same project session before taking work.

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
- which meeting conflicts require user direction before development can start
- which agent should take each task
- whether the implementation agent has inherited the kickoff meeting context

## Goals

- Convert completed meeting minutes into a structured delivery plan.
- Represent task dependencies explicitly.
- Represent pending user decisions as a kickoff approval gate before development starts.
- Block development task generation/start until the kickoff decision gate is resolved.
- Assign tasks to the intended agent role.
- Require assigned agents to resume the same project session used during kickoff.
- Prevent concurrent task execution from sharing and corrupting the same agent session.
- Persist task execution outputs so dependent agents receive concrete upstream artifacts, not only status changes.
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
- `source_meeting_id`
- `source_requirement_id`
- `meeting_snapshot`
- `status`

The backend validates that the dependency graph has no cycles. A task is `ready` only when:

- every task in `depends_on_task_ids` is completed

Tasks whose dependencies are unmet stay visible on the board, but they show a blocked reason and cannot be claimed or started.

### 2. How do user decisions appear on the board, and do they block other steps?

User decisions are not long-lived task blockers. They are a one-time kickoff decision gate.

The gate is built from the meeting's disputed items:

- `pending_user_decisions`
- unresolved `conflict_points`
- moderator `supplementary` notes that ask for user direction

The board should show a `Kickoff Decision Required` card or panel for the meeting. It asks the user to choose a direction for each unresolved meeting conflict, for example:

- cooldown vs resource skill system
- defer elemental counters vs include them in MVP
- fixed QA sample battle vs simulation-based balance acceptance

Before the user resolves this kickoff gate:

- no delivery tasks should be started
- no agent should claim implementation work
- the board can show a draft delivery plan preview, but it is not actionable

After the user resolves the kickoff gate:

- the selected directions are saved into the delivery plan
- the final development task DAG is generated or regenerated from the resolved directions
- any pre-resolution task preview must be revalidated against the resolved directions before it can become actionable
- there should be no remaining `pending_user_decisions` during development
- user involvement resumes at review/acceptance, not during normal implementation

### 3. Are implementation agents the same agents from the meeting, and do they receive the meeting spirit?

They must use the same project-scoped agent session.

Kickoff creates per-agent project sessions. Meeting participants such as `design`, `dev`, and `qa` use those sessions during the meeting. Generated tasks are assigned to agent roles, and execution should look up the same `project_id + agent` session before calling Claude.

Because the same session is resumed, an agent that attended the meeting already has its own meeting context in Claude's session history. Task execution should not resend the full meeting minutes or "meeting spirit" as a large prompt attachment by default.

Each task may store a compact `meeting_snapshot` built from the meeting minutes for board display, audit, and debugging:

- meeting title
- relevant decisions
- relevant consensus points
- task-specific acceptance notes

When the assigned agent starts work, the prompt should include the task itself and lightweight references such as `task_id`, `meeting_id`, and `requirement_id`, while resuming the same project session. This makes session continuity the source of meeting memory.

If the owner agent did not attend the meeting but still has a project session, it can receive the compact `meeting_snapshot` because it does not have the same firsthand meeting context. This is an exception, not the default for agents that attended.

If no project session exists, task execution must fail clearly. It should not create an ad hoc session or silently run without meeting context.

Because the same project-scoped session is the context carrier, the system must not run two tasks concurrently against the same `project_id + agent` session. A same-agent task must acquire a session lease before execution; if another task already holds that lease, the task stays queued or `ready` with a clear "agent session busy" reason. This avoids interleaving unrelated task prompts into one Claude conversation.

## Recommended Approach

Add a small delivery-planning layer instead of overloading `MeetingMinutes` or immediately mutating the original `RequirementCard`.

New backend concepts:

- `DeliveryPlan`: one plan generated from one meeting.
- `DeliveryTask`: a task in the plan, with dependencies and owner.
- `KickoffDecisionGate`: a one-time user direction gate for unresolved meeting conflicts.
- `TaskExecutionResult`: persisted output from one completed delivery task.
- `AgentSessionLease`: short-lived lock for one `project_id + agent` Claude session.

The web board can then show a combined project view:

- requirement cards
- delivery task cards
- kickoff decision gate cards/panels

This avoids squeezing task dependencies and kickoff decision state into the existing `RequirementCard` schema, while still making the result visible on the board.

## Alternatives Considered

### Option 1: Convert action items directly into RequirementCards

Pros:

- Fastest implementation.
- Reuses current board columns.

Cons:

- `RequirementCard` has no dependency fields.
- No first-class kickoff decision gate.
- Easy to accidentally send unresolved conflicts into development.
- Blurs parent requirement vs implementation task.

### Option 2: Store only enriched meeting minutes

Pros:

- Minimal backend changes.
- Keeps Meeting Graph output simple.

Cons:

- Board still does not show actionable work.
- User cannot resolve kickoff meeting conflicts from the board.
- Agents still lack task-level session continuity.

### Option 3: Add DeliveryPlan, DeliveryTask, and KickoffDecisionGate

Pros:

- Models dependencies correctly.
- Models kickoff user decisions as a pre-development gate.
- Keeps original requirements intact.
- Supports agent assignment and project-session continuity.
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
  "status": "awaiting_user_decision",
  "task_ids": ["task_combat_loop", "task_skill_system"],
  "decision_gate_id": "gate_meeting_8fab476c",
  "decision_resolution_version": null,
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Plan statuses:

- `awaiting_user_decision`: meeting conflicts need user direction before development.
- `active`: visible and actionable on the board.
- `completed`: all tasks complete.
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
  "execution_result_id": null,
  "output_artifact_ids": [],
  "acceptance_criteria": [
    "A 3v3 battle can complete with win/loss result.",
    "Turn order follows speed sorting."
  ],
  "meeting_snapshot": {
    "meeting_title": "Turn-Based Combat MVP Kickoff Meeting Minutes",
    "relevant_decisions": ["Core combat loop locked to 3v3 with fixed speed sorting"],
    "relevant_consensus": ["Three action types confirmed: Normal Attack, Skill, Defend"],
    "task_acceptance_notes": ["Turn order follows speed sorting."]
  },
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Task statuses:

- `preview`: non-actionable pre-resolution task draft.
- `blocked`: task dependencies are unresolved.
- `ready`: can be claimed by the owner agent.
- `in_progress`: assigned agent is executing.
- `review`: implementation output is ready for QA/review.
- `done`: completed.
- `cancelled`: removed from scope.

### KickoffDecisionGate

Stored at:

```text
.studio-data/kickoff_decision_gates/<gate_id>.json
```

Example:

```json
{
  "id": "gate_meeting_8fab476c",
  "plan_id": "plan_meeting_8fab476c",
  "meeting_id": "meeting_8fab476c",
  "requirement_id": "req_8fab476c",
  "project_id": "proj_123",
  "status": "open",
  "resolution_version": 0,
  "items": [
    {
      "id": "decision_skill_cost",
      "question": "Should MVP skills use cooldowns or a resource cost?",
      "context": "Meeting left skill cost system unresolved. Dev needs this before skill framework implementation.",
      "options": ["cooldown", "resource", "defer skills"],
      "resolution": null
    }
  ],
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

Gate statuses:

- `open`: waiting for user.
- `resolved`: user resolved every conflict direction.
- `cancelled`: no longer needed.

### TaskExecutionResult

Stored at:

```text
.studio-data/task_execution_results/<result_id>.json
```

Example:

```json
{
  "id": "result_task_combat_loop",
  "task_id": "task_combat_loop",
  "plan_id": "plan_meeting_8fab476c",
  "project_id": "proj_123",
  "agent": "dev",
  "session_id": "claude-session-id",
  "summary": "Implemented deterministic 3v3 combat loop with attack, skill, defend, and win/loss resolution.",
  "output_artifact_ids": ["artifact_combat_loop_patch"],
  "changed_files": ["studio/combat/loop.py", "tests/test_combat_loop.py"],
  "tests_or_checks": ["uv run pytest tests/test_combat_loop.py"],
  "follow_up_notes": [],
  "created_at": "2026-04-22T12:30:00Z"
}
```

### AgentSessionLease

Stored at:

```text
.studio-data/agent_session_leases/<project_id>_<agent>.json
```

Example:

```json
{
  "id": "proj_123_dev",
  "project_id": "proj_123",
  "agent": "dev",
  "task_id": "task_combat_loop",
  "session_id": "claude-session-id",
  "status": "held",
  "expires_at": "2026-04-22T13:00:00Z",
  "created_at": "2026-04-22T12:00:00Z"
}
```

Lease rules:

- A task may start only if no active lease exists for the same `project_id + agent`.
- Lease acquisition and task status update should be treated as one atomic operation at the repository/service level.
- A lease must be released when the task reaches `review`, `done`, `blocked`, `ready`, `cancelled`, or execution fails.
- Expired leases can be recovered by the backend with an explicit warning in logs.

## Generation Flow

### Trigger

Generation happens after a completed meeting.

Entry points:

- Backend API: `POST /api/meetings/{meeting_id}/delivery-plan`
- Web UI button on a meeting detail panel: `Generate Delivery Plan`
- Future automatic option after kickoff, but not in the first implementation

The first implementation should require explicit user action. This prevents accidental task creation from a meeting with bad or incomplete minutes.

If the meeting has unresolved `pending_user_decisions`, generation creates an `awaiting_user_decision` plan and an open `KickoffDecisionGate`. It may create a non-actionable draft preview of tasks, but no task can be started until the gate is resolved.

If the meeting has no unresolved user decisions, generation can create an `active` plan immediately.

Pre-resolution task previews are optional and must use `status = "preview"`. They are for user understanding only. When the kickoff gate is resolved, the backend must either:

- regenerate the final task DAG from the meeting plus gate resolutions
- or validate every preview task against the gate resolutions and stamp the plan with the matching `decision_resolution_version`

If validation cannot prove that a preview task matches the chosen direction, discard or regenerate it. Do not silently activate stale preview tasks.

### Planner Agent

Add a profile-backed role:

```text
delivery_planner
```

`delivery_planner` is a normal managed agent. It must have an explicit registered agent profile and Claude project folder configuration before use. If that configuration is missing, plan generation fails clearly. Do not fallback to an unconfigured prompt or reuse another agent's profile.

The planner consumes:

- `MeetingMinutes`
- source `RequirementCard`
- project id if available
- kickoff gate resolutions when present

It returns strict JSON:

```json
{
  "tasks": [
    {
      "title": "...",
      "description": "...",
      "owner_agent": "dev",
      "depends_on": ["Other task title or temporary key"],
      "acceptance_criteria": ["..."],
      "source_evidence": ["decision/action item text from minutes"]
    }
  ],
  "decision_gate": {
    "items": [
    {
      "question": "...",
      "context": "...",
      "options": ["..."],
      "source_evidence": ["pending decision text from minutes"]
    }
    ]
  }
}
```

The backend normalizes temporary keys into persisted ids, validates dependencies, and computes initial task status.

### Deterministic Guardrails

The backend must apply these rules after planner output:

- Owner agent must be one of `design`, `dev`, `qa`, `art`, `reviewer`, or `quality`.
- `delivery_planner` itself must be registered in the agent config before generation starts.
- Tasks cannot depend on unknown tasks.
- Dependency graph must be acyclic.
- A task with incomplete task dependencies starts as `blocked`.
- A task with no blockers starts as `ready`.
- Pending user decisions from `MeetingMinutes.pending_user_decisions` must become kickoff gate items or be explicitly resolved before plan activation.
- `conflict_points` are context only. They become kickoff gate items only when they also appear in `pending_user_decisions`, `unresolved_conflicts`, or another explicit moderator field that marks them unresolved.
- `conflict_points` should not become development tasks unless a decision resolved them or the minutes contain a clear decision.

## Board Behavior

Add a board mode or section for delivery planning.

Columns:

- `Kickoff Decision Needed`: open kickoff gate cards/panels.
- `Blocked`: delivery tasks blocked by dependencies.
- `Ready`: tasks available for the assigned agent.
- `In Progress`: claimed/running tasks.
- `Review`: output ready for QA/review.
- `Done`: completed tasks.

Task cards show:

- title
- owner agent
- source meeting id
- dependency count
- acceptance criteria preview

Kickoff decision gate cards show:

- unresolved meeting conflict questions
- options for each question
- source meeting id
- resolution action for the whole gate

When the user resolves the kickoff gate:

- update `KickoffDecisionGate.status` to `resolved`
- store all chosen directions
- increment and store `KickoffDecisionGate.resolution_version`
- regenerate or validate the final delivery tasks using those directions
- stamp activated tasks/plan with the matching `decision_resolution_version`
- set `DeliveryPlan.status` to `active`
- broadcast board update

## Blocking Rules

Tasks are blocked if any of these are true:

- the plan's kickoff decision gate is still open
- `depends_on_task_ids` contains a task not in `done`.
- required project-agent session is missing.
- the required `project_id + owner_agent` session lease is held by another running task.

Blocked tasks remain visible. They cannot be claimed by agents.

Once the kickoff decision gate is resolved, development should not introduce new user-decision blockers. User involvement returns at review and acceptance stages.

## Agent Execution Session Continuity

When a task is started by its owner agent:

1. Load `DeliveryTask`.
2. Load source `MeetingMinutes`.
3. Load source `RequirementCard`.
4. Load project-agent session by `project_id + owner_agent`.
5. Acquire a lease for `project_id + owner_agent`.
6. Build a minimal task prompt from:
   - task title and description
   - acceptance criteria
   - dependency outputs if available
   - `task_id`
   - `meeting_id`
   - `requirement_id`
7. Invoke the assigned agent using the same project session.
8. Save execution output, produced artifact ids, completion summary, logs, and status.
9. Release the session lease.

The execution agent may or may not have attended the kickoff meeting:

- If the owner agent attended, it uses the same project session and receives only the minimal task prompt. The meeting context is already in that session.
- If the owner agent did not attend, it still uses the project session if one exists and may receive the compact `meeting_snapshot`.
- If no session exists, fail clearly. Do not run without meeting context.

This keeps the execution prompt small and makes same-session continuity the primary mechanism for preserving meeting context.

### Dependency Output Handoff

A dependency is not satisfied by status alone. When a task moves to `done`, it must persist a task execution result containing:

- `task_id`
- `agent`
- `session_id`
- `summary`
- `output_artifact_ids`
- `changed_files` if code was changed
- `tests_or_checks`
- `follow_up_notes`

Downstream task prompts should include compact summaries and artifact ids from completed dependencies. They should not re-send the whole upstream conversation, but they do need the concrete upstream outputs.

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
  "decision_gate": {}
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
  "decision_gate": {}
}
```

### Resolve Kickoff Decision Gate

```http
POST /api/kickoff-decision-gates/{gate_id}/resolve?workspace=<workspace>
```

Body:

```json
{
  "resolutions": {
    "decision_skill_cost": "Use cooldowns for MVP skills."
  }
}
```

Response includes updated gate, activated plan, and generated tasks.

### Start Task

```http
POST /api/delivery-tasks/{task_id}/start?workspace=<workspace>
```

Rules:

- task must be `ready`
- owner agent session must exist
- plan kickoff gate must be resolved
- task `decision_resolution_version` must match the plan's current `decision_resolution_version`
- owner agent session lease must be available
- task becomes `in_progress`
- execution can be queued in the existing agent pool

## Frontend Changes

Add or extend board UI:

- Add `Generate Delivery Plan` action on meeting detail.
- Add delivery board columns for kickoff decision gates and tasks.
- Show blockers directly on cards.
- Add kickoff decision resolution dialog.
- Add task detail panel with `meeting_snapshot` and source meeting links.
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
- Open kickoff decision gate blocks task start.
- Missing project session blocks task start.
- Busy owner agent session blocks or queues task start.
- Stale preview task with mismatched decision resolution version blocks task start.
- Agent execution failure moves task back to `ready` or `blocked` with error detail, depending on blocker state.

## Tests

Backend tests:

- Generate delivery plan from completed meeting.
- Reject generation for missing or draft meeting.
- Reject invalid planner output.
- Reject cyclic dependencies.
- Create kickoff decision gate from meeting conflicts and pending user decisions.
- Plan with an open kickoff gate is not actionable.
- Resolve kickoff gate and activate the delivery plan.
- Resolve kickoff gate regenerates or validates final task DAG and stamps `decision_resolution_version`.
- Start task fails when kickoff gate is open.
- Start task fails when decision resolution version is stale.
- Start task fails when dependency task is not done.
- Start task uses the owner agent's project session.
- Start task fails or queues when the owner agent session lease is already held.
- Start task sends only a minimal task prompt when the owner agent attended the meeting.
- Start task can include compact `meeting_snapshot` only when the owner agent did not attend.
- Completed task stores execution result and output artifact ids.
- Downstream task prompt includes dependency execution summaries and artifact ids.

Frontend tests:

- Delivery board lists kickoff decision gate and task cards.
- Open kickoff gate blocks task start.
- Gate resolution activates task cards.
- Ready task shows `Start Agent Work`.
- Blocked task hides/disables `Start Agent Work`.
- Task detail shows `meeting_snapshot` and source meeting links.

Manual acceptance:

- Run a kickoff meeting.
- Generate a delivery plan from the completed meeting.
- Verify a kickoff decision gate appears for unresolved meeting conflicts.
- Resolve all kickoff gate decisions.
- Verify the delivery plan becomes active and tasks can start.
- Start a ready dev task.
- Verify the dev agent resumes the same project session id used during kickoff.
- Start two tasks assigned to the same agent and verify the second does not run concurrently in the same session.
- Complete an upstream task and verify a dependent task receives the upstream execution summary/artifact ids.

## Acceptance Criteria

- Completed meeting minutes can be converted into a delivery plan.
- Delivery plan preserves task dependencies as an acyclic graph.
- Pending user decisions appear on the board as a kickoff decision gate.
- Open kickoff decision gate blocks development task start.
- Once kickoff decisions are resolved, development proceeds without additional user-decision blockers until review/acceptance.
- Task owner agent is explicit and limited to registered agents.
- Task execution uses the project-scoped agent session.
- Task execution uses the same project-scoped agent session as kickoff.
- Task execution prompt stays minimal for agents that attended the meeting.
- Same project-agent session is protected by a lease so concurrent tasks cannot interleave one Claude session.
- Completed tasks persist execution outputs that downstream tasks can reference.
- Pre-resolution task previews cannot become actionable unless regenerated or validated against the chosen kickoff decisions.
- `delivery_planner` has explicit agent configuration and fails clearly if missing.
- The board makes blockers, dependencies, and owner agents visible.
- Existing Meeting Graph, project session, and requirements board behavior remain intact.
