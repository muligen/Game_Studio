# Claude Workflow Agents Design

## Goal

Replace the current stub workflow agents with Claude Agent SDK-backed implementations while preserving the current backend-first kernel architecture, local JSON persistence model, CLI-first workflow, and deterministic fallback behavior.

## Scope

This change covers:

- `studio.agents.design.DesignAgent`
- `studio.agents.dev.DevAgent`
- `studio.agents.qa.QaAgent`
- `studio.agents.quality.QualityAgent`
- `studio.agents.reviewer.ReviewerAgent`
- `studio.agents.art.ArtAgent`
- `studio.agents.worker.WorkerAgent` migration onto the same shared Claude adapter pattern

This change does not cover:

- `studio.agents.planner.PlannerAgent`
- New storage entities or major schema redesign
- Image generation integration for `art`
- Replacing domain/state-machine logic with LLM behavior

## Problem

The project has already evolved beyond a demo graph into a backend-first collaboration kernel, but most non-planner agents are still deterministic stubs that only emit trace markers. The demo `worker` node already has a working Claude Agent SDK integration with config loading, structured parsing, thread isolation, and subprocess fallback. The rest of the workflow should use the same LLM execution path without weakening the CLI, tests, or current deterministic guarantees.

## Recommended Approach

Introduce a shared role-based Claude adapter in `studio.llm` and move all non-planner workflow agents onto it.

The shared adapter will own:

- `.env` configuration loading
- Claude Agent SDK invocation
- subprocess fallback for the blocking `os.getcwd` case
- structured output parsing and validation
- role-specific prompt generation

Each agent will continue to own:

- extracting context from `RuntimeState.goal`
- converting validated Claude output into `NodeResult`
- deterministic fallback payloads when Claude is disabled or fails

## Architecture

### Shared Claude Role Adapter

Add a new adapter that generalizes the current `ClaudeWorkerAdapter` pattern.

Responsibilities:

- accept a role name such as `worker`, `design`, `dev`, `qa`, `quality`, `reviewer`, or `art`
- build a role-specific prompt from runtime input
- declare a role-specific structured output schema
- call Claude Agent SDK with the existing project-root, env, and mode settings
- parse and validate the result into a typed Python payload
- surface a stable error type compatible with current fallback handling

The current `ClaudeWorkerAdapter` should either become a thin compatibility wrapper over the new role adapter or be refactored into reusable base logic so the project ends with one Claude integration path, not two.

### Agent Responsibilities

Each non-planner workflow agent will:

1. Read the required context from `RuntimeState.goal`
2. Invoke the shared Claude role adapter
3. Produce a `NodeResult` with:
   - a stable `decision`
   - a minimal `state_patch`
   - optional artifacts where appropriate
   - trace metadata including `llm_provider`, `fallback_used`, and any fallback reason
4. Fall back to deterministic behavior when Claude is disabled, misconfigured, unavailable, or returns invalid output

### Dispatcher

`studio.runtime.dispatcher.RuntimeDispatcher` should continue lazy-loading agents and should not gain role-specific LLM logic. LLM concerns remain inside `studio.llm` and agent classes.

## Role Output Contracts

To minimize schema churn, agents should first return structured payloads that map cleanly onto the current runtime model.

### Worker

Keep the existing `design_brief` artifact shape:

- `title`
- `summary`
- `genre`

### Reviewer

Return structured review output that can drive `continue` vs `retry`:

- `decision`
- `reason`
- `risks`

### Design

Return a compact design drafting payload:

- `title`
- `summary`
- `core_rules`
- `acceptance_criteria`
- `open_questions`

### Dev

Return implementation-oriented output:

- `summary`
- `changes`
- `risks`
- `self_test_notes`

### QA

Return validation-oriented output:

- `summary`
- `passed`
- `findings`
- `suggested_bug`

### Quality

Return release-readiness output:

- `summary`
- `ready`
- `risks`
- `followups`

### Art

Return art-direction text only:

- `summary`
- `style_direction`
- `asset_list`

## Error Handling and Fallbacks

The system must remain safe to run in local development and CI without live Claude access.

Fallback triggers:

- `GAME_STUDIO_CLAUDE_ENABLED=false`
- missing API key or invalid mode
- Claude SDK import/runtime failures
- subprocess failures
- invalid structured output

Fallback behavior:

- produce deterministic payloads per agent
- preserve existing graph and CLI behavior
- mark traces with:
  - `llm_provider: "claude"`
  - `fallback_used: true`
  - `fallback_reason: <error>`

Successful Claude runs should set `fallback_used: false`.

## Testing Strategy

Implementation must follow test-first development.

Add or update tests for:

- shared role adapter structured parsing and validation
- role-specific prompts and output parsing
- each agent's Claude success path
- each agent's fallback path when disabled
- each agent's fallback path on Claude errors
- reviewer decision mapping
- runtime/dispatcher compatibility where needed

Existing tests must keep passing with:

```powershell
uv run pytest -q
```

Tests must not require real network access or real Claude credentials.

## Constraints

- Keep `planner` deterministic
- Do not move domain state-machine rules into prompts
- Do not make CLI behavior depend on online LLM availability
- Keep `graph` as the legacy demo runtime entrypoint
- Keep new workflow entrypoints centered on `studio/interfaces/cli.py`

## Implementation Outline

1. Add shared Claude role adapter and typed payload models
2. Migrate `worker` onto the shared adapter without changing external behavior
3. Replace `reviewer` stub with Claude-backed structured review
4. Replace `design`, `dev`, `qa`, `quality`, and `art` stubs with Claude-backed implementations
5. Update or extend tests role by role
6. Run the full test suite
