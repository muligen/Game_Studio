# Langfuse Observability Integration Design

## Context

Game Studio currently uses LangGraph to coordinate multi-agent workflows and
Claude Agent SDK for most live LLM calls. Local debugging is supported by
`studio/runtime/llm_logs.py`, which records prompt, context, and reply payloads
under the workspace.

The main runtime entry points are:

- `studio/runtime/graph.py` for LangGraph workflow orchestration.
- `studio/llm/claude_roles.py` for role-based Claude Agent SDK calls.
- `studio/llm/claude_worker.py` for the older worker adapter path.
- `studio/runtime/llm_logs.py` for local LLM debug logs.

Langfuse should add cross-run observability without replacing the local log
files or changing existing fallback behavior.

## Goals

- Trace each workflow run from graph start through node completion.
- Capture each agent node as a span with node metadata, fallback state, and
  errors.
- Capture Claude Agent SDK calls, including prompt, context, structured output,
  model, mode, session metadata, failures, and latency.
- Preserve trace continuity for subprocess-based Claude calls.
- Keep local development and tests working when Langfuse is disabled or
  unconfigured.
- Avoid leaking API keys, secrets, tokens, or excessive workspace payloads.

## Non-Goals

- Replacing `LlmRunLogger`.
- Building frontend Langfuse dashboards in this phase.
- Changing agent behavior, graph routing, fallback policy, or prompt content.
- Migrating the project from Claude Agent SDK to LangChain chat models.

## Recommended Approach

Use a hybrid integration:

1. Add a small internal observability module that owns Langfuse configuration,
   no-op behavior, redaction, and context propagation.
2. Add explicit graph and node spans in `studio/runtime/graph.py`.
3. Use Langfuse's Claude Agent SDK/OpenTelemetry integration around live Claude
   calls in `studio/llm/claude_roles.py` and `studio/llm/claude_worker.py`.
4. Keep local `llm_logs` and enrich entries with Langfuse trace metadata when
   available.

This approach is preferred over a LangGraph-only callback because the current
LLM calls are not primarily made through LangChain chat models. It is preferred
over prompt/reply-only manual logging because the Claude Agent SDK integration
can expose lower-level execution details, tool use, errors, and timings.

## Configuration

Add these variables to `.env.example`:

```env
GAME_STUDIO_LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
GAME_STUDIO_LANGFUSE_CAPTURE_IO=true
GAME_STUDIO_LANGFUSE_SAMPLE_RATE=1.0
```

Behavior:

- Disabled by default.
- Missing Langfuse keys disable external export instead of failing startup.
- `LANGFUSE_HOST` supports both Langfuse Cloud and self-hosted deployments.
- `GAME_STUDIO_LANGFUSE_CAPTURE_IO=false` records metadata but omits prompt,
  context, and reply payloads.

## New Module

Create `studio/observability/langfuse.py`.

Responsibilities:

- Read project `.env` using the same lightweight dotenv style already used by
  the Claude adapters.
- Expose a config object with enabled state, host, keys, capture settings, and
  sample rate.
- Initialize Langfuse/OpenTelemetry only when enabled and keys are present.
- Provide no-op context managers when disabled.
- Provide helpers for graph traces, node spans, and LLM observations.
- Redact sensitive keys and truncate large payloads before sending them.
- Provide an environment propagation helper for subprocess calls.

Suggested public surface:

```python
class LangfuseTelemetry:
    def graph_trace(self, *, name: str, metadata: dict[str, object]): ...
    def node_span(self, *, name: str, metadata: dict[str, object]): ...
    def llm_observation(self, *, name: str, metadata: dict[str, object]): ...
    def subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]: ...
    def current_metadata(self) -> dict[str, object]: ...
```

The exact implementation may use context managers, decorators, or thin wrapper
functions as long as call sites remain small and readable.

## Graph Instrumentation

Instrument `studio/runtime/graph.py` at workflow and node boundaries.

Trace names:

- `game_studio_demo`
- `studio_design_workflow`
- `studio_delivery_workflow`
- `studio_meeting_workflow`

Trace metadata:

- `run_id`
- `project_id`
- `requirement_id`
- `workspace_root`
- `graph`

Node span metadata:

- `node_name`
- `task_id`
- `agent_role`
- `fallback_used`
- `fallback_reason`
- `decision`
- `status`

Node spans should record concise input and output summaries. They should not
send full workspace state, full artifact payloads, or full meeting transcript
history unless `GAME_STUDIO_LANGFUSE_CAPTURE_IO=true` and payload size limits
allow it.

## Claude Agent SDK Instrumentation

Instrument `studio/llm/claude_roles.py` around:

- `ClaudeRoleAdapter.generate`
- `ClaudeRoleAdapter._generate_payload`
- `ClaudeRoleAdapter.chat`
- `ClaudeRoleAdapter._chat`
- `ClaudeRoleAdapter._generate_payload_via_subprocess`
- `ClaudeRoleAdapter._chat_via_subprocess`

Each LLM observation should include:

- `role_name`
- `model`
- `mode`
- `session_id`
- `resume_session`
- `claude_project_root`
- sanitized context
- structured output or reply summary
- error message when the call fails

The Claude Agent SDK/OpenTelemetry integration should run inside the current
Langfuse trace/span so internal SDK spans are attached to the same workflow.

Subprocess calls must receive Langfuse and OpenTelemetry environment context.
If context propagation is unavailable, subprocess calls may create their own
trace, but they must include `parent_run_id`, `role_name`, and `task_id`
metadata so traces can still be correlated.

## Legacy Worker Instrumentation

Instrument `studio/llm/claude_worker.py` around:

- `ClaudeWorkerAdapter.generate_design_brief`
- `ClaudeWorkerAdapter._generate_design_brief`
- `ClaudeWorkerAdapter._generate_design_brief_via_subprocess`

This keeps the demo runtime and any older worker path visible in Langfuse.

## Local Log Enrichment

Keep `studio/runtime/llm_logs.py` as the local source of truth for offline
debugging. Extend log entries with Langfuse metadata when available:

```json
{
  "langfuse_trace_id": "...",
  "langfuse_observation_id": "...",
  "langfuse_url": "..."
}
```

The log writer must continue to work when these fields are absent.

## Redaction and Payload Limits

Before exporting data, recursively redact values for keys containing:

- `api_key`
- `secret`
- `token`
- `password`
- `ANTHROPIC_API_KEY`
- `LANGFUSE_SECRET_KEY`

Large strings and nested payloads should be truncated to a fixed limit. The
first implementation should prefer concise summaries over full objects for
graph state and workspace data.

## Error Handling

Langfuse must not change product behavior.

- Initialization failure downgrades to no-op telemetry.
- Export failure is swallowed or logged as a warning.
- Missing credentials disable Langfuse export.
- Claude failures continue through existing `ClaudeRoleError` and fallback
  paths.
- Test runs do not require network access or Langfuse credentials.

## Testing

Automated tests:

- Disabled Langfuse behaves as no-op.
- Enabled Langfuse with missing keys does not fail startup or agent execution.
- Sensitive fields are redacted.
- Large payloads are truncated.
- Claude role calls create LLM observation metadata through the wrapper.
- Subprocess environment includes Langfuse/OpenTelemetry propagation fields when
  telemetry is active.
- Existing graph tests pass without Langfuse configuration.

Manual verification:

1. Configure Langfuse credentials in `.env`.
2. Run:

   ```powershell
   uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
   ```

3. Exercise requirement, meeting, design, and delivery flows from the Web UI.
4. Confirm Langfuse shows one trace per workflow run with node spans and Claude
   observations.
5. Confirm local `llm_logs` still contain prompt, context, reply, and optional
   Langfuse metadata.

## Implementation Sequence

1. Add Langfuse dependency and update `.env.example`.
2. Add `studio/observability/langfuse.py` with no-op-first behavior.
3. Add unit tests for config parsing, redaction, truncation, and no-op mode.
4. Instrument `studio/llm/claude_roles.py`.
5. Instrument `studio/llm/claude_worker.py`.
6. Instrument `studio/runtime/graph.py` node spans.
7. Enrich `studio/runtime/llm_logs.py` with optional Langfuse metadata.
8. Update README with setup and verification instructions.
9. Run unit tests and one manual Langfuse-enabled workflow.

## Acceptance Criteria

- All existing tests pass without Langfuse credentials.
- With Langfuse enabled, a demo run appears in Langfuse with graph and node
  structure.
- Meeting workflow traces correlate moderator and participating agent calls.
- Claude errors and fallback states are visible in trace metadata.
- Local LLM logs continue to be written.
- No API keys, secrets, or tokens are exported.
- Subprocess Claude calls are trace-correlated with their parent workflow.
