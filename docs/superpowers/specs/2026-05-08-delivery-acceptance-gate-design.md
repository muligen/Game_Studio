# Delivery Acceptance Gate Design

## Summary

Delivery must stop treating QA, reviewer, and quality outputs as ordinary successful tasks. A requirement is complete only after an automated acceptance gate proves every requirement-level acceptance criterion with concrete evidence, including the basic guarantee that the generated game can start and open without fatal runtime errors.

The gate runs after implementation tasks finish. It builds and starts the target project, drives it through Playwright, records screenshots, videos, logs, command output, and criterion-level results, then either accepts the requirement or creates bug-fix tasks. Bug fixes run through the same Delivery DAG runner and the gate repeats until all criteria pass or the repair budget is exhausted.

## Post-Merge MVP Status

Merged commit `def68eb` implements the core acceptance gate loop:

- acceptance schemas and JSON repositories;
- acceptance contract builder;
- build/test/preview command detection;
- Playwright startup smoke validation;
- deterministic evaluator;
- Delivery LangGraph `acceptance_gate` node;
- automatic `bug_fix` task creation and bounded repair attempts;
- `accepted` and `needs_attention` plan states;
- board-level acceptance run visibility and retry.

The merged MVP intentionally stops short of the full target in a few places. Install commands are detected but not executed before build/test/preview. Acceptance artifacts are stored as evidence paths inside `AcceptanceRun`, but there is no dedicated artifact download endpoint yet. The board shows latest validation status and failed criteria, but does not yet show a full artifact browser. Dedicated Langfuse spans for the acceptance phases are still a follow-up; local persistence is already in place through `acceptance_runs` and task events.

## Goals

- Confirm every requirement acceptance criterion has an explicit pass or fail result.
- Require evidence for each passed criterion, not just an LLM summary.
- Prove the generated game starts, opens in a browser, and has no fatal console or page errors.
- Automatically create bug-fix tasks from failed criteria and re-run validation after fixes.
- Keep the user in the Delivery board instead of requiring manual bug creation or manual test judgment.
- Preserve existing task dependency behavior and project-scoped execution.
- Make Langfuse and local debug data show the validation run, evidence, failed criteria, and repair loop.

## Non-Goals

- This does not replace human product acceptance for subjective direction changes.
- This does not require perfect game-specific automation for every possible genre.
- This does not make visual taste fully deterministic. Visual requirements can pass only when evidence and an evaluator explain the match.
- This does not change Clarify or Meeting semantics except that their acceptance criteria become part of the acceptance contract.

## Current Problem

The current Delivery runner marks a task done whenever `complete_task()` is called. The runner extracts `summary`, `checks`, and `follow_ups` from agent telemetry, but it does not fail the plan when QA returns `passed=false`, quality returns `ready=false`, reviewer returns a negative decision, or the agent falls back to deterministic output.

After all tasks are `done`, the plan is immediately marked `completed`, and the requirement is transitioned to `done`. This means a requirement can pass even when test agents produced fallback output or no real evidence. The acceptance gate fixes that by moving completion responsibility out of ordinary tasks and into a deterministic validation phase.

## User Interaction

The Delivery board shows a new final section named **Acceptance Gate**.

The visible flow becomes:

1. `Implementing`: normal Delivery tasks run according to dependencies.
2. `Validating`: the gate builds, starts, and inspects the generated project.
3. `Repairing`: failed criteria produce bug-fix tasks.
4. `Revalidating`: the gate runs again after fixes.
5. `Accepted`: all criteria pass with evidence.
6. `Needs Attention`: automatic repair attempts are exhausted or the project cannot be validated.

The target user experience shows:

- Overall gate status: `pending`, `running`, `failed`, `repairing`, `passed`, or `needs_attention`.
- Repair attempt count, for example `1/3`.
- One row per criterion with status, evidence count, and failure reason.
- Command logs from build, test, and preview. Install execution is a follow-up even though install commands are detected.
- Playwright screenshot evidence, browser console/page errors, and retained video files when the browser context records them.
- Browser console errors and page errors.
- Auto-created bug-fix tasks linked to the failed criteria.

The user does not need to approve each bug loop. The only user intervention states are:

- validation cannot determine how to start the project;
- automatic repair budget is exhausted;
- a criterion is subjective enough that automated evidence is inconclusive;
- the project repeatedly fails before Playwright can open a page.

## Acceptance Contract

Before validation, the system builds an immutable `AcceptanceContract` for the plan. It contains normalized criteria from:

- `RequirementCard.acceptance_criteria`;
- Clarify `meeting_context.acceptance_criteria` when present;
- Meeting decisions and consensus points that contain acceptance wording;
- resolved kickoff decision gate items;
- each Delivery task `acceptance_criteria`;
- system-required startup criteria.

System-required startup criteria are always included:

- the project has a detectable start or preview command;
- dependencies can be installed or are already available;
- the project builds when a build command exists;
- automated tests pass when a test command exists;
- the browser page opens successfully;
- no fatal `pageerror` is raised;
- no console error matching fatal runtime, module load, syntax, or uncaught exception patterns appears;
- the main app root, canvas, or visible game surface exists;
- the page is not visually blank.

Each contract item records:

- `id`;
- `source`;
- `text`;
- `required_evidence_types`;
- `severity`: `blocker`, `major`, or `minor`;
- `owner_hint`: `dev`, `art`, `qa`, `reviewer`, or `quality`.

Only `blocker` and `major` failures block completion by default. Startup criteria are always `blocker`.

## Validation Runner

The validation runner executes in the project directory, not in the Game Studio repository.

The full target runner performs these stages:

1. Detect project type and package manager from files in `project_dir`.
2. Install dependencies only when required by the project state.
3. Run build command when available.
4. Run test command when available.
5. Start preview or dev server on an allocated port.
6. Use Playwright to open the app.
7. Capture console messages, page errors, screenshot, video, DOM summary, route failures, and selected pixel checks.
8. Evaluate each acceptance criterion against command evidence, browser evidence, file evidence, and optional QA/quality LLM interpretation.
9. Save an `AcceptanceRun` with all evidence and criterion results.

The merged MVP runs stages 1, 3, 4, 5, 6, and core evidence capture. It detects install commands but does not execute them yet. DOM summaries, route failure summaries, selected pixel checks, explicit video evidence rows, and optional LLM interpretation remain follow-up work.

Command detection order for Node projects:

- package manager: `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`, then `npm`;
- install: `pnpm install --frozen-lockfile`, `yarn install --frozen-lockfile`, or `npm ci`;
- build: `package.json.scripts.build`;
- test: `package.json.scripts.test`, skipping only when the script is absent or exactly an unimplemented placeholder command;
- preview: `preview`, `start`, then `dev`.

The preview process is always started as a child process managed by the server process cleanup layer.

## Criterion Evaluation

Every criterion receives:

- `status`: `passed`, `failed`, or `inconclusive`;
- `evidence`: list of evidence ids;
- `reason`;
- `repair_hint`;
- `owner_hint`;
- `blocking`: boolean.

A criterion cannot be `passed` without at least one evidence item. QA fallback, quality fallback, missing test output, and empty `tests_or_checks` cannot produce a pass.

Evaluation is deterministic first:

- startup criteria are checked directly from command and Playwright results;
- build and test criteria use command exit codes;
- UI-open criteria use Playwright page state;
- file/artifact criteria use file existence and changed-file evidence.

LLM interpretation is allowed only as a secondary evaluator for criteria that cannot be mapped deterministically. The LLM receives the contract, command outputs, Playwright evidence summaries, screenshots, task results, and project file index. Its output cannot override a deterministic startup failure.

## Bug Loop

If any blocking criterion fails:

1. The plan moves to `repairing`.
2. The service creates one or more `bug_fix` Delivery tasks.
3. Each bug task depends on the task most likely responsible for the failed criterion and on the latest validation run.
4. The bug task context includes failed criteria, logs, screenshot path, video path, console errors, page errors, and repair hints.
5. Bug tasks run through existing project-scoped agent execution.
6. After bug tasks finish, the gate runs again.

The default repair limit is three validation attempts, including the first validation run. It is configurable with `GAME_STUDIO_ACCEPTANCE_MAX_ATTEMPTS`. When the limit is reached and blocking failures remain, the plan becomes `needs_attention` and the requirement is not marked done.

## State Model

Delivery plan status adds:

- `validating`;
- `repairing`;
- `accepted`;
- `needs_attention`.

The existing `completed` status remains for backward compatibility, but new Delivery flows should use `accepted` for successful requirement completion. A plan may be shown as completed in API compatibility fields only after acceptance passes.

Delivery task kind adds:

- `delivery`;
- `bug_fix`;
- `acceptance`.

Acceptance run status:

- `running`;
- `passed`;
- `failed`;
- `needs_attention`.

Requirement transition changes:

- implementation tasks done -> requirement remains `implementing`;
- acceptance passed -> requirement transitions to `done`;
- acceptance failed with repair budget remaining -> requirement remains `implementing`;
- acceptance exhausted -> requirement transitions to `quality_check` or remains `implementing` with board state `needs_attention`.

## API And Board Contract

Merged MVP Delivery board response adds:

- `acceptance_runs`;
- `runner_status`: includes `validating`, `repairing`, `accepted`, and `needs_attention`.

Merged MVP API endpoints:

- `GET /api/delivery-plans/{plan_id}/acceptance-runs`;
- `GET /api/acceptance-runs/{run_id}`;
- `POST /api/delivery-plans/{plan_id}/retry-acceptance`.

Follow-up endpoints:

- `GET /api/acceptance-runs/{run_id}/artifacts/{artifact_id}`;
- optional contract detail endpoint if the board needs to render pending criteria before the first run.

The existing retry endpoint remains for individual failed tasks. The new acceptance retry endpoint re-runs the gate after a user or developer manually fixes project files.

## Observability

Target Langfuse spans:

- `delivery:acceptance_gate`;
- `delivery:acceptance:commands`;
- `delivery:acceptance:playwright`;
- `delivery:acceptance:evaluate`;
- `delivery:bug_loop:create_task`.

Merged MVP persists acceptance evidence locally but does not yet create those dedicated Langfuse spans. Add them when the local acceptance run shape is stable.

Metadata includes:

- `plan_id`;
- `requirement_id`;
- `project_id`;
- `project_dir`;
- `acceptance_run_id`;
- `attempt_number`;
- `failed_criteria_count`;
- `blocking_failure_count`;
- `repair_task_ids`.

Local task events include:

- `acceptance_contract_created`;
- `acceptance_run_started`;
- `acceptance_command_finished`;
- `acceptance_browser_opened`;
- `acceptance_criterion_passed`;
- `acceptance_criterion_failed`;
- `acceptance_bug_task_created`;
- `acceptance_run_passed`;
- `acceptance_run_failed`;
- `acceptance_needs_attention`.

## Testing Strategy

Unit tests cover:

- contract builder deduplicates criteria from requirement, meeting, gate, and task sources;
- startup criteria are always included;
- deterministic startup failure blocks acceptance;
- criterion cannot pass without evidence;
- QA fallback, quality fallback, and reviewer negative output block acceptance;
- bug-fix tasks are created from failed criteria;
- repair budget stops loops and marks `needs_attention`;
- accepted plans are the only new plans allowed to mark requirements done.

Integration tests cover:

- a mock project that builds and opens passes acceptance;
- a mock project with a syntax error fails Playwright validation and creates a bug task;
- a bug task fixes the syntax error and the next validation passes;
- Delivery board includes criterion results, evidence summaries/paths, and repair attempts.

End-to-end tests cover:

- mock Delivery plan produces a simple browser game project;
- acceptance gate starts it with Playwright;
- screenshot and video are retained;
- console/page errors fail the run;
- after automatic repair, requirement reaches done only when all blocking criteria pass.

## Open Decisions

- Default repair limit is three attempts unless changed by env.
- The first implementation should support Node/Vite-style web projects because current generated games are browser projects.
- Non-web project validation can be marked inconclusive and `needs_attention` until a project-specific verifier is added.
- Human product acceptance remains out of scope for this gate.

## Self-Review

- No unresolved placeholder language remains.
- The design keeps completion semantics consistent: requirement done only after acceptance passes.
- The bug loop has a fixed stopping rule and visible user state.
- The Playwright validation requirement is explicit and blocks startup failures.
