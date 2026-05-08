# Delivery Non-Blocking Assumptions Design

## Summary

Remove the normal Delivery decision gate from the default Clarify -> Meeting -> Delivery path. Once Clarify has enough information to make the requirement executable, Delivery should not stop again for implementation preferences. Agents should make reasonable default decisions, record them as project assumptions, continue execution, and deliver project documentation that explains what was assumed, why, and how to change it in a later iteration.

The only blocking state left is `Needs Attention`, used after the system has attempted to proceed and cannot continue safely or technically. It is not a pre-delivery question prompt.

## Acceptance Gate Dependency

The acceptance gate MVP is now merged into `main`. This design should integrate with those states instead of inventing another completion path:

- Delivery still executes without a normal user decision gate.
- After tasks finish, the plan moves through `validating`, `repairing`, `accepted`, or `needs_attention`.
- A requirement reaches `done` only after the acceptance gate marks the plan `accepted`.
- Planner or agent assumptions must be written into task context and project docs before validation so the gate can evaluate the actual chosen direction.

## Problem

The current Delivery decision gate is too weak and too disruptive:

- It appears after tasks have already been split.
- Resolving it only changes task status from preview to ready or blocked.
- It records `decision_resolution_version` and injects `resolved_decisions` into task context.
- It does not regenerate tasks.
- It does not rewrite task descriptions, acceptance criteria, dependencies, or final project documentation.

This creates a mismatch in the UI. The user makes a decision, but the visible task plan barely changes. The interaction feels like a required approval step without strong product value.

## Principle

Clarify is the place for required user input. Delivery is the place for autonomous execution.

If the user did not specify a preference during Clarify and the requirement is still executable, the system should choose a sensible default. The default must be visible, documented, and traceable, but it should not block execution.

The new rule is:

> Development does not ask. Delivery documents assumptions. Validation proves the result. Iteration changes defaults later.

## Goals

- Remove the normal `Kickoff Decision Needed` blocking column from new Delivery flows.
- Stop generating Delivery decision gates for ordinary implementation preferences.
- Let agents choose default style, technology, scope details, and test strategy when the user left them open.
- Record every automatic decision as an assumption with rationale and impact.
- Include project documentation in every delivered project.
- Preserve a `Needs Attention` escape hatch for cases that cannot be resolved automatically.
- Make the board show assumptions and documentation status instead of blocking questions.

## Non-Goals

- Do not remove Clarify questions that are required to make the requirement executable.
- Do not remove all human intervention forever; keep post-failure `Needs Attention`.
- Do not hide assumptions inside prompts only.
- Do not require a user approval loop before Delivery starts.
- Do not rewrite existing historical plans; the new behavior applies to new plans.

## New User Flow

The default flow becomes:

1. Clarify gathers only blocking requirements.
2. Meeting agents discuss and produce a project direction.
3. Delivery planner generates the final task DAG directly.
4. Agents execute tasks using project-scoped context.
5. Agents record assumptions and decisions as they work.
6. Delivery includes documentation tasks.
7. Acceptance gate validates startup, tests, and requirement criteria.
8. The requirement becomes done only after acceptance passes.

There is no normal `Decision Needed` stop between Meeting and Delivery.

## Assumptions

An assumption is a structured project decision made by agents when the user did not specify a detail.

Each assumption records:

- `id`;
- `requirement_id`;
- `project_id`;
- `source`: `meeting`, `planner`, `agent`, or `acceptance`;
- `category`: `product`, `art`, `tech`, `qa`, `scope`, or `delivery`;
- `decision`;
- `rationale`;
- `impact`;
- `owner_agent`;
- `change_policy`: usually `next_iteration`;
- `created_at`.

Examples:

- `Art direction defaults to retro pixel style because it fits Snake MVP, is cheap to implement, and is easy to validate visually.`
- `The web implementation defaults to Vite + React + Canvas because current generated browser games already use this path.`
- `The first version includes three test levels to keep MVP scope small while proving progression.`

Assumptions are not questions. They do not pause the runner.

## Project Documentation

Every delivered project must include project documentation under the target `project_dir`, not under Game Studio.

Required documents:

- `docs/PROJECT_BRIEF.md`: goal, scope, core gameplay, target platform.
- `docs/DECISIONS.md`: confirmed user decisions and automatic assumptions with rationale.
- `docs/ACCEPTANCE.md`: acceptance criteria, validation evidence, and final acceptance status.
- `docs/RUNBOOK.md`: install, run, test, build, and troubleshooting instructions.
- `docs/ITERATION_NOTES.md`: suggested follow-up changes and assumption overrides for later requests.

Delivery planner should create documentation tasks when the implementation plan lacks them. These docs are part of the final deliverable and acceptance gate should check that they exist.

## Needs Attention

`Needs Attention` replaces blocking decision gates for exceptional cases.

It is allowed only when the system cannot safely or technically proceed after trying reasonable defaults or repair loops.

Examples:

- Missing API key or external account required by the requirement.
- License or asset rights risk that cannot be avoided with a default.
- User request contains contradictory hard constraints.
- Generated project cannot install, start, or open after automatic repair attempts.
- A required external dependency is unavailable.

`Needs Attention` includes:

- concrete blocker;
- evidence;
- attempted assumptions or repair attempts;
- recommended user action;
- affected tasks;
- whether a later retry can resume automatically.

It should not be used for ordinary preferences such as visual style, library choice, layout direction, level count, or naming.

## Planner Behavior

Delivery planner no longer returns a normal `decision_gate` for new plans.

Instead, it returns:

- final `tasks`;
- `assumptions`;
- optional `needs_attention` only for true blockers;
- documentation task coverage.

Task descriptions must be materialized with defaults:

- good: `Implement Snake MVP with the default retro pixel art direction.`
- bad: `Implement Snake MVP after user chooses pixel or minimal style.`

Task acceptance criteria must include chosen assumptions when relevant:

- `UI uses the documented retro pixel direction.`
- `RUNBOOK documents how to run the Vite web app.`

Task dependencies remain real DAG dependencies. Documentation tasks may depend on implementation and validation tasks when they summarize final outputs.

## Agent Behavior

Every Delivery agent receives:

- requirement context;
- meeting decisions;
- assumptions so far;
- dependency results;
- current task;
- project directory;
- documentation requirements.

Agents must:

- proceed autonomously;
- avoid asking user questions;
- make smallest reasonable assumptions;
- write assumptions into the structured assumption store when they materially affect product, tech, art, QA, or scope;
- update relevant docs when their task changes project behavior.

Agents must not:

- call AskQuestion for normal Delivery ambiguity;
- stop because the user did not choose a style or library;
- leave branch-like wording in deliverables.

## Board Interaction

Delivery board changes:

- Remove `Kickoff Decision Needed` column for new plans.
- Add `Assumptions & Decisions` panel.
- Show assumption count and categories.
- Show documentation task status.
- Show `Needs Attention` only when a real blocker occurs.

The panel shows:

- automatic decision;
- rationale;
- impacted tasks;
- owner agent;
- change policy.

Users can review assumptions during execution but are not required to respond.

Optional UI action:

- `Change in next iteration`: creates a change request seeded with the assumption to override.

This action does not mutate the running Delivery plan.

## API And Storage

New storage:

- `project_assumptions` repository.

New schema:

- `ProjectAssumption`.

Delivery board response adds:

- `assumptions`;
- `needs_attention_items`;
- documentation coverage summary.

Existing `KickoffDecisionGate` schema can remain for backward compatibility and old plans. New plans should not generate gates unless a legacy compatibility flag is enabled.

## Backward Compatibility

Existing open decision gates can still be resolved through the old endpoint.

New Delivery plan generation should:

- default to non-blocking assumptions;
- not create `KickoffDecisionGate` for normal preferences;
- return `decision_gate: null`;
- make initial task statuses `ready` or `blocked` based on real dependencies.

Feature flag:

- `GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE=false` by default.

If enabled, the old gate path can remain temporarily for comparison and migration.

## Observability

Langfuse and local debug metadata should show:

- assumptions generated by planner;
- assumptions generated by each agent;
- tasks impacted by each assumption;
- docs written or updated;
- Needs Attention events and evidence.

Suggested span/event names:

- `delivery:assumption_created`;
- `delivery:documentation_task_created`;
- `delivery:needs_attention`;
- `delivery:assumption_override_requested`.

## Tests

Unit tests:

- planner output with ordinary preferences creates assumptions, not decision gates;
- plan with assumptions starts active immediately;
- task context includes assumptions;
- agents cannot call AskQuestion for normal Delivery ambiguity;
- documentation tasks are created when missing;
- `Needs Attention` is only produced for configured blocker categories.

Integration tests:

- Clarify -> Meeting -> Delivery runs without decision gate when style is unspecified;
- generated task descriptions include default decisions;
- assumptions appear in Delivery board response;
- project docs are generated in `project_dir/docs`;
- acceptance gate checks required documentation.

E2E tests:

- user asks for a simple Snake MVP without specifying style;
- Delivery starts automatically;
- board shows assumptions instead of a decision gate;
- final project contains `PROJECT_BRIEF.md`, `DECISIONS.md`, `ACCEPTANCE.md`, `RUNBOOK.md`, and `ITERATION_NOTES.md`;
- accepted project can be started and opened.

## Migration Plan

1. Add assumption schema and storage.
2. Update planner prompt and payload to return assumptions instead of normal decision gates.
3. Update plan service to create active plans when only assumptions exist.
4. Keep old decision gate endpoint for old plans.
5. Add board assumptions panel and remove the gate column for new plans.
6. Add documentation task requirements.
7. Wire assumptions into task context and project docs.
8. Add tests and E2E coverage.

## Self-Review

- No blocking Delivery question remains in the normal path.
- Clarify remains responsible for true requirement blockers.
- Assumptions are structured, visible, and documented.
- Needs Attention is reserved for technical or safety blockers after attempts to proceed.
- Final delivery includes project documentation and can be validated by the acceptance gate.
