# AI Studio Collaboration Kernel Design

## Summary

This spec defines phase 1 of the AI game studio system as a backend-first collaboration kernel built around structured workflow objects, command-style CLI operations, local file persistence, and LangGraph-based execution visibility.

The goal is not a fully autonomous AI company. The goal is a human-led workflow system where AI agents draft and execute work, while the user can inspect, edit, approve, reject, send back, and reprioritize key artifacts throughout the process.

## Goals

- Replace the current demo-only workflow with a reusable collaboration kernel.
- Make requirement flow and bug flow first-class state machines.
- Expose structured workflow objects instead of only freeform artifact payloads.
- Provide a command-style CLI as the primary interaction surface.
- Preserve `langgraph dev` support so key execution paths remain observable.
- Keep the architecture ready for a later UI without requiring a redesign of the backend.

## Non-Goals

- No database in phase 1.
- No web UI in phase 1.
- No autonomous swarm handoff model.
- No automated merge, deploy, or production operations.
- No full company simulation with executive roles.
- No requirement that the art workflow be part of the phase 1 critical path.

## Project Context

The current repository already contains:

- A LangGraph runtime with a simple `planner -> worker -> reviewer` demo graph.
- Filesystem-backed artifact, memory, and checkpoint storage.
- A Typer CLI entrypoint.
- LangGraph Studio integration through `studio/langgraph_app.py`.
- Test coverage around runtime execution, CLI behavior, schemas, storage helpers, and Claude worker fallback behavior.

The current implementation is still demo-oriented. Business entities such as requirements, design docs, balance tables, and bug cards do not yet exist as first-class models. Approval gates, state-machine rules, and board-centric workflow control are also not implemented yet.

## Design Principles

### Human-in-the-loop first

The user is an active participant, not a passive observer. The system must expose structured artifacts and workflow state so the user can review, edit, approve, reject, send back, and reprioritize work.

### Board-centric workflow

The system should treat requirement and bug boards as the center of workflow state. Conversation is optional; stateful objects and transitions are the source of truth.

### Structured artifacts over opaque text

Design outputs must be editable structured objects rather than one large generated blob. This enables user intervention, deterministic validation, and easier downstream automation.

### Clear separation of concerns

Business rules, storage, agent behavior, CLI behavior, and LangGraph orchestration should remain separate so each can evolve without forcing a rewrite of the others.

### Local-first development

Phase 1 should use filesystem persistence and CLI workflows so the system stays inspectable, scriptable, and easy to test.

## Proposed Architecture

The system should be reorganized into four layers:

1. Domain layer
   - Owns workflow entities, state-machine rules, approval rules, and orchestration services.
   - Has no dependency on CLI or LangGraph.

2. Storage layer
   - Owns local JSON persistence and query helpers.
   - Provides repositories for workflow objects and logs.

3. Agent layer
   - Owns agent-specific generation and execution behavior.
   - Produces patches, summaries, test results, and recommendations, but does not define workflow legality.

4. Interface and runtime layer
   - CLI is the primary user interface.
   - LangGraph remains the execution and observability layer for agent-driven workflow steps.

## Directory and Module Shape

This design keeps the existing runtime structure but introduces domain-focused modules.

- `studio/schemas`
  - Add dedicated schema modules for:
  - `requirement.py`
  - `bug.py`
  - `design_doc.py`
  - `balance_table.py`
  - `action_log.py`

- `studio/domain`
  - `requirement_flow.py`
  - `bug_flow.py`
  - `approvals.py`
  - `services.py`

- `studio/storage`
  - JSON-backed repositories for requirements, design docs, balance tables, bugs, and logs.

- `studio/agents`
  - Expand from `planner/worker/reviewer` toward:
  - `design.py`
  - `dev.py`
  - `qa.py`
  - `quality.py`
  - `art.py`

- `studio/runtime`
  - Replace the demo-centric graph assembly with workflow execution graphs that operate on stored entities.

- `studio/interfaces/cli.py`
  - Becomes the command-style board operations entrypoint.

- `studio/langgraph_app.py`
  - Continues to expose runnable graphs for `langgraph dev`.

## Core Workflow Objects

### RequirementCard

Represents the lifecycle of a user requirement.

Required fields:

- `id`
- `title`
- `type`
- `priority`
- `status`
- `owner`
- `design_doc_id`
- `balance_table_ids`
- `bug_ids`
- `notes`

Phase 1 statuses:

- `draft`
- `designing`
- `pending_user_review`
- `approved`
- `implementing`
- `self_test_passed`
- `testing`
- `pending_user_acceptance`
- `quality_check`
- `done`

### DesignDoc

Represents a structured, editable planning artifact.

Required fields:

- `id`
- `requirement_id`
- `title`
- `summary`
- `core_rules`
- `acceptance_criteria`
- `open_questions`
- `status`

Phase 1 status values:

- `draft`
- `pending_user_review`
- `approved`
- `sent_back`

### BalanceTable

Represents an editable table of tuning values associated with a requirement or design doc.

Required fields:

- `id`
- `requirement_id`
- `table_name`
- `columns`
- `rows`
- `locked_cells`
- `status`

Phase 1 status values:

- `draft`
- `pending_user_review`
- `approved`
- `sent_back`

### BugCard

Represents issues discovered during testing or verification.

Required fields:

- `id`
- `requirement_id`
- `title`
- `severity`
- `status`
- `reopen_count`
- `owner`
- `repro_steps`
- `notes`

Phase 1 status values:

- `new`
- `fixing`
- `fixed`
- `verifying`
- `closed`
- `reopened`
- `needs_user_decision`

### ActionLog

Represents workflow history and audit events.

Required fields:

- `id`
- `timestamp`
- `actor`
- `action`
- `target_type`
- `target_id`
- `message`
- `metadata`

## Persistence Model

Phase 1 should use local JSON storage under a dedicated workspace directory such as `.studio-data`.

Example layout:

- `.studio-data/requirements/req_001.json`
- `.studio-data/design_docs/design_001.json`
- `.studio-data/balance_tables/balance_001.json`
- `.studio-data/bugs/bug_001.json`
- `.studio-data/logs/log_001.json`

Each object is stored independently. Relationships are maintained by id references, not by nesting the full object graph into a single file.

This layout keeps the system easy to inspect manually, easy to test, and ready for later replacement with a different storage backend if needed.

## CLI Design

The CLI is the primary interface in phase 1. It should be command-oriented instead of hiding workflow changes behind a single `run-demo` style command.

Representative command groups:

- `requirement create`
- `requirement list`
- `requirement show`
- `requirement reprioritize`
- `design show`
- `design edit`
- `design approve`
- `design send-back`
- `balance show`
- `balance edit`
- `balance approve`
- `workflow run-design`
- `workflow run-dev`
- `workflow run-qa`
- `workflow run-quality`
- `bug list`
- `bug show`
- `bug decide`
- `log list`

Phase 1 CLI output should default to human-readable summaries. A machine-oriented JSON mode can be added where helpful, but is not the primary UX.

## Approval and Send-Back Rules

The domain layer should enforce approval gates as hard rules.

Key requirements:

- A requirement cannot enter implementation until the related design doc is approved.
- If a requirement uses balance tables, required balance tables must be approved before implementation.
- A testing failure creates or updates a bug and sends the requirement back to implementation.
- A user can still send work back during user acceptance after tests pass.
- All approve, reject, send-back, and reprioritize actions must write action logs.

Phase 1 should prefer explicit errors for invalid transitions rather than silent correction.

## Requirement Flow

The requirement flow in phase 1 is:

- `draft`
- `designing`
- `pending_user_review`
- `approved`
- `implementing`
- `self_test_passed`
- `testing`
- `pending_user_acceptance`
- `quality_check`
- `done`

Allowed regressions:

- `pending_user_review -> designing`
- `testing -> implementing`
- `pending_user_acceptance -> implementing`
- `quality_check -> implementing`

The exact transition guard logic should live in `studio/domain/requirement_flow.py`, not in CLI commands and not inside agents.

## Bug Flow

The bug flow in phase 1 is:

- `new`
- `fixing`
- `fixed`
- `verifying`
- `closed`
- `reopened`
- `needs_user_decision`

Escalation to `needs_user_decision` occurs when one or more of the following are true:

- `reopen_count >= 3`
- severity is high enough to require human review
- estimated fix cost is too large
- user experience risk is high

Phase 1 can implement the first two conditions deterministically and support the latter two through explicit CLI or agent-provided flags.

## Agent Responsibilities

### Design agent

Inputs:

- Requirement goal
- project constraints
- relevant history

Outputs:

- `DesignDoc`
- one or more `BalanceTable` drafts when applicable
- acceptance criteria
- open questions for the user

### Dev agent

Inputs:

- approved requirement
- approved design doc
- approved balance tables when required

Outputs:

- implementation summary
- changed-work summary
- self-test summary
- testing focus notes

### QA agent

Inputs:

- requirement
- design doc
- implementation summary

Outputs:

- test cases
- test results
- bug cards on failure

### Quality agent

Inputs:

- requirement board
- bug board
- action logs

Outputs:

- process risk alerts
- repeated-failure alerts
- escalation recommendations

### Art agent

Phase 1 should define the art agent schema and placeholder interface, but art execution does not need to block the main requirement-development-test-quality loop.

## LangGraph Strategy

LangGraph remains part of the system, but it should no longer be the only place where business meaning exists.

Phase 1 should expose runnable graphs for key execution paths such as:

- design generation
- development execution
- qa execution
- quality scan

CLI commands trigger these graphs. The graphs read from repositories, call the relevant domain services and agents, then persist updated workflow objects and logs.

This preserves `langgraph dev` observability while keeping workflow correctness in the domain layer.

## Error Handling

Phase 1 error handling should favor consistency over partial success.

Rules:

- Invalid state transitions fail fast with explicit errors.
- Repository writes should avoid partial multi-object updates where possible.
- Agent execution failures should be logged and leave objects in a recoverable state.
- CLI commands should surface actionable messages rather than raw stack traces in normal expected failure cases.

## Testing Strategy

Phase 1 test coverage should expand in three layers.

### Schema tests

- Validation rules
- defaults
- enum values
- extra-field rejection

### Domain tests

- legal and illegal requirement transitions
- legal and illegal bug transitions
- approval gate enforcement
- send-back behavior
- bug escalation to `needs_user_decision`
- logging side effects

### Integration tests

- CLI workflow from requirement creation to design generation
- approval gates before development
- QA failure generating bug cards
- quality scan generating alerts when conditions are met
- `studio.langgraph_app` exposing runnable graphs for LangGraph Studio

## Incremental Delivery Plan

Implementation should proceed in this order:

1. Add core schemas and ids
2. Add repositories and local storage layout
3. Add requirement and bug state machines
4. Add approval, send-back, and reprioritize services
5. Add action logging
6. Add command-style CLI operations
7. Replace the demo graph with workflow graphs that operate on stored entities
8. Expand tests for schema, domain, CLI, and LangGraph paths
9. Add minimal art-agent placeholders without making them critical-path blockers

## Acceptance Criteria

Phase 1 is complete when all of the following are true:

- A user can create a new requirement from the CLI.
- The design workflow can generate a structured design doc and balance draft.
- The user can inspect and edit the generated design objects.
- The user must approve required planning artifacts before implementation can start.
- Development execution can run only on approved inputs.
- QA execution can generate bugs and send the requirement back when testing fails.
- Repeated bug reopen events can trigger user-decision escalation.
- Logs capture approvals, send-backs, state changes, and workflow execution events.
- `langgraph dev` still exposes the workflow graphs for local inspection.

## Open Decisions Carried Forward

These are intentionally deferred, not unresolved blockers:

- Whether balance-table editing should support field-level patch commands only, or also full-object replacement commands.
- Whether quality risk thresholds should be fully configurable in phase 1 or hard-coded first.
- Whether art artifacts in phase 1 should be plain structured text or support richer asset references.

These choices should be made during implementation planning, but they do not block this design.
