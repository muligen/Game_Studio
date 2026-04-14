# Claude Agent SDK Worker Integration Design

## Summary

This document defines the first integration of Claude Agent SDK into the Game Studio Runtime Kernel. The scope is intentionally narrow: only the `worker` node will be upgraded from a hard-coded demo implementation to an LLM-backed implementation. The goal is to preserve the existing runtime structure while replacing the worker's static artifact generation with a Claude-driven design brief generator.

The integration is designed as a text-first worker with a clear expansion path to tool-enabled operation later. For this phase, the worker remains responsible for producing a structured `design_brief` artifact. Claude Agent SDK usage will be isolated behind a small adapter layer so the runtime and graph assembly do not need to know Claude-specific details.

## Goals

- Replace the hard-coded `WorkerAgent` content generation with Claude Agent SDK
- Preserve the current runtime graph shape and node contracts
- Keep the worker output schema stable for downstream reviewer and artifact storage logic
- Support a safe fallback path when Claude SDK is unavailable or produces unusable output
- Leave room for future tool-enabled worker behavior without enabling broad file mutation in this phase

## Non-Goals

- Integrating Claude into `planner` or `reviewer`
- Allowing the worker to freely edit repository files by default
- Building a generalized multi-provider LLM abstraction
- Reworking the runtime graph, dispatcher, or checkpoint architecture
- Depending on live Claude access in automated tests

## Current Project Context

The current `WorkerAgent` in `studio/agents/worker.py` produces a fixed `ArtifactRecord` from `goal.prompt`. This is useful for testing the runtime shell but not for exercising a real LLM-backed node.

The runtime architecture already has a good seam for this work:

- `RuntimeDispatcher` resolves agents by node name
- `WorkerAgent.run()` returns a `NodeResult`
- the graph layer persists artifacts and merges state externally

This means the Claude integration can remain local to the worker implementation and a new Claude-specific adapter module.

## Recommended Approach

Introduce a Claude worker adapter module and keep `WorkerAgent` as the business-facing runtime node.

### Why this approach

- It preserves the current runtime boundaries
- It prevents Claude SDK details from leaking into the graph layer
- It keeps the worker readable and testable
- It creates a reusable pattern for future planner and reviewer upgrades

## Alternatives Considered

### Option 1: Put Claude SDK calls directly inside `WorkerAgent.run()`

Trade-offs:

- Pros: smallest initial diff
- Cons: mixes runtime business logic, SDK setup, parsing, and error handling in one place

### Option 2: Add a dedicated Claude worker adapter and call it from `WorkerAgent` (recommended)

Trade-offs:

- Pros: best balance of clarity, isolation, and extensibility
- Cons: slightly more code than the direct approach

### Option 3: Move model selection into dispatcher-level wiring

Trade-offs:

- Pros: cleaner future swapping between implementations
- Cons: too much indirection for the current project size

## Architecture

The worker remains the runtime node entrypoint, but delegates model invocation to a Claude adapter.

```text
Runtime graph
  -> WorkerAgent.run(state)
  -> Claude worker adapter
  -> Claude Agent SDK
  -> structured design payload
  -> ArtifactRecord
  -> NodeResult
```

## Component Design

### 1. `WorkerAgent`

`WorkerAgent` stays in `studio/agents/worker.py`.

Responsibilities:

- validate `goal.prompt`
- decide whether Claude-backed execution is enabled
- call the Claude worker adapter
- convert structured output into `ArtifactRecord`
- return `NodeResult`
- record fallback or error metadata in `trace`

`WorkerAgent` should not:

- know low-level Claude SDK invocation details
- parse arbitrary conversational output inline
- manage tool permissions directly

### 2. Claude Worker Adapter

Add a Claude-specific module such as:

- `studio/llm/claude_worker.py`

Responsibilities:

- define the Claude Agent SDK invocation path
- encapsulate `ClaudeAgentOptions(...)` construction
- manage text-first versus tool-enabled mode selection
- extract and validate the expected structured payload
- map SDK failures into Python exceptions or explicit error signals

This adapter is the only place that should directly depend on Claude Agent SDK.

### 3. Worker Configuration

The integration should support explicit configuration so local development stays predictable.

Recommended configuration dimensions:

- whether Claude-backed execution is enabled
- worker mode: `text` or `tools_enabled`
- Claude model identifier if needed
- whether project settings are allowed
- optional timeout or execution controls

For this phase, the recommended default is:

- Claude enabled only when explicitly configured
- mode defaults to `text`

This keeps normal local testing stable even without Claude credentials.

## Worker Behavior

### Default Mode: Text-First

The worker sends the prompt and runtime context to Claude and expects a structured design brief payload.

Expected payload fields:

- `title`
- `summary`
- `genre`

This payload is then mapped into:

- `artifact_type = "design_brief"`
- `source_node = "worker"`
- `payload = {...}`

### Future Expansion Mode: Tool-Enabled

The design keeps room for a later `tools_enabled` mode where Claude Agent SDK can use project-aware tools such as file inspection. That mode is not the default for this phase and should not be required to complete this integration.

This phase only needs the configuration seam and adapter structure to support it later.

## Prompting And Output Contract

Claude should be instructed to return a compact JSON object matching the worker payload contract. The Python side should treat model output as untrusted until it is parsed and validated.

Recommended contract:

```json
{
  "title": "string",
  "summary": "string",
  "genre": "string"
}
```

The runtime should not depend on free-form prose parsing for this first integration. If Claude returns anything outside the expected shape, the adapter should treat it as invalid output.

## Fallback Strategy

Fallback behavior is important because this project must remain runnable even when Claude SDK is not available locally.

### Fallback Triggers

- Claude Agent SDK package is unavailable
- SDK invocation fails
- required credentials or local setup are missing
- Claude response cannot be parsed into the required JSON shape
- required fields are missing after parsing

### Fallback Behavior

When fallback is enabled, the worker should produce the current deterministic demo artifact so the graph can still complete.

Fallback should also annotate trace information, for example:

- `llm_provider = "claude"`
- `fallback_used = true`
- `fallback_reason = "..."`

This keeps Studio debugging and runtime observation useful without making the graph brittle.

## Error Handling

Errors should be separated into two categories:

### Recoverable For This Phase

- missing Claude environment
- transient SDK failure
- invalid model output

These should use deterministic fallback when fallback is enabled.

### Non-Recoverable Configuration Errors

- explicitly configured Claude-only mode with fallback disabled
- invalid local configuration values

These may raise a runtime error or produce a typed error path, depending on implementation preference. The key requirement is that the behavior must be explicit and testable.

## Testing Strategy

Automated tests must not require live Claude access.

### Unit Tests

- worker returns structured artifact when adapter returns valid payload
- worker falls back to stub output when adapter fails and fallback is enabled
- worker rejects non-string `goal.prompt`
- worker trace includes fallback metadata when applicable

### Adapter Tests

- adapter builds Claude request from prompt and context
- adapter rejects malformed output
- adapter extracts expected JSON payload shape

These tests should use mocks or fakes around the SDK boundary.

### Runtime Integration Tests

Existing graph and CLI tests should continue to pass without requiring Claude setup.

If Claude mode is configuration-gated, integration tests can monkeypatch the adapter to simulate Claude success and failure while verifying runtime behavior remains stable.

## File Changes

Likely additions:

- `studio/llm/__init__.py`
- `studio/llm/claude_worker.py`
- new worker-focused tests for Claude-backed behavior

Likely modifications:

- `studio/agents/worker.py`
- `pyproject.toml`
- `README.md`

## Security And Safety Notes

- Tool-enabled behavior must not be the default in this phase
- Repository mutation tools should not be broadly enabled without a separate design pass
- Claude output must be validated before entering runtime state or artifact storage

## Success Criteria

This work is successful when:

- the `worker` node can use Claude Agent SDK to generate a structured design brief
- the runtime graph and dispatcher shape remain unchanged
- local development without Claude still works through a documented fallback path
- tests cover both Claude success and fallback behavior
- the design leaves a clean path for later `tools_enabled` expansion

## Final Recommendation

Integrate Claude Agent SDK only into the `worker` node for now. Keep `WorkerAgent` as the runtime-facing node, add a dedicated Claude adapter module to isolate SDK details, default to a text-first structured output contract, and preserve a deterministic fallback so the runtime remains stable in local development and automated testing.
