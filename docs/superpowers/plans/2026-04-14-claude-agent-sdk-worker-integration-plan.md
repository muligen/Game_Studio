# Claude Agent SDK Worker Integration Plan

> Approved spec: `docs/superpowers/specs/2026-04-14-claude-agent-sdk-worker-design.md`

**Goal:** Replace the hard-coded `worker` node with a Claude Agent SDK-backed implementation that reads configuration from a project-root `.env`, preserves the existing runtime graph contract, and falls back to the current deterministic design brief when Claude is unavailable or misconfigured.

**Architecture:** Keep `WorkerAgent` as the runtime-facing node, add a small Claude adapter under `studio/llm/`, load `.env` configuration explicitly, validate Claude output into a strict structured payload, and preserve stable graph/CLI behavior through deterministic fallback.

**Tech Stack:** Python 3.12, Claude Agent SDK, Pydantic v2, Typer, pytest, pytest-mock, optional `.env` loading helper

---

## Planned File Changes

Add:

- `studio/llm/__init__.py`
- `studio/llm/claude_worker.py`
- `.env.example`
- `tests/test_claude_worker.py`

Modify:

- `studio/agents/worker.py`
- `pyproject.toml`
- `README.md`

Optional if needed for clean config handling:

- `studio/config/__init__.py`
- `studio/config/claude.py`

## Task 1: Add Failing Tests For Claude Worker Integration

**Files:**
- Create: `tests/test_claude_worker.py`
- Modify if needed: existing worker tests

- [ ] **Step 1: Add tests for configuration and fallback behavior**

Cover at least:

- worker returns Claude-generated payload when adapter succeeds
- worker falls back to deterministic artifact when `.env` is missing or incomplete
- worker falls back when Claude adapter raises an error
- worker rejects non-string `goal.prompt`
- worker trace records fallback metadata

- [ ] **Step 2: Run the targeted tests to verify failure**

Run:

```batch
uv run pytest -q tests/test_claude_worker.py
```

Expected:

- import errors or failing assertions until implementation exists

## Task 2: Add Claude SDK Dependency And Configuration Example

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`

- [ ] **Step 1: Add the Claude Agent SDK dependency**

Update `pyproject.toml` so the project can import the SDK and any `.env` helper if needed.

- [ ] **Step 2: Add `.env.example`**

Include the keys defined by the approved spec:

```env
GAME_STUDIO_CLAUDE_ENABLED=false
GAME_STUDIO_CLAUDE_MODE=text
GAME_STUDIO_CLAUDE_MODEL=
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
```

- [ ] **Step 3: Sync dependencies and verify installation**

Run:

```batch
uv sync
```

Expected:

- dependency installation succeeds

## Task 3: Implement Claude Worker Adapter

**Files:**
- Create: `studio/llm/__init__.py`
- Create: `studio/llm/claude_worker.py`

- [ ] **Step 1: Implement `.env` loading and config parsing**

The adapter layer should:

- read from project-root `.env`
- parse `GAME_STUDIO_CLAUDE_ENABLED`
- parse `GAME_STUDIO_CLAUDE_MODE`
- parse optional model
- parse `ANTHROPIC_API_KEY`
- parse `ANTHROPIC_BASE_URL`

Design note:

- keep config loading small and explicit
- if a dedicated config module is not necessary, keep it local to the adapter

- [ ] **Step 2: Implement Claude invocation wrapper**

The adapter should:

- accept the runtime prompt/context
- construct Claude Agent SDK options
- invoke the SDK
- request compact JSON output
- parse the returned JSON into a structured payload

- [ ] **Step 3: Implement structured validation**

Validate that Claude output contains:

- `title`
- `summary`
- `genre`

Reject invalid output and surface an adapter-level error for fallback handling.

## Task 4: Upgrade `WorkerAgent` To Use Claude With Deterministic Fallback

**Files:**
- Modify: `studio/agents/worker.py`

- [ ] **Step 1: Preserve current deterministic artifact generation as fallback**

Extract or retain the current hard-coded artifact payload so it can be used when:

- Claude is disabled
- `.env` is missing or incomplete
- Claude invocation fails
- Claude output is invalid

- [ ] **Step 2: Call the Claude adapter when enabled**

`WorkerAgent.run()` should:

- validate `goal.prompt`
- decide whether Claude mode is enabled
- call the adapter
- build `ArtifactRecord` from Claude payload on success
- record trace metadata about Claude or fallback path

- [ ] **Step 3: Keep the runtime contract unchanged**

Ensure the returned `NodeResult` still contains:

- `decision = continue`
- `state_patch["plan"]["current_node"] = "worker"`
- one `design_brief` artifact

## Task 5: Document `.env` Setup And Runtime Behavior

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Claude worker setup instructions**

Document:

- `.env` location
- required keys
- optional `ANTHROPIC_BASE_URL`
- how fallback works when Claude is disabled or unavailable

- [ ] **Step 2: Add a minimal example flow**

Show:

- copying `.env.example` to `.env`
- enabling Claude worker
- running the CLI demo
- verifying fallback versus Claude-backed output

## Task 6: Verify Runtime And Regression Safety

**Files:**
- Tests only

- [ ] **Step 1: Run focused worker tests**

Run:

```batch
uv run pytest -q tests/test_claude_worker.py tests/test_agent_adapters.py
```

- [ ] **Step 2: Run graph and CLI regression tests**

Run:

```batch
uv run pytest -q tests/test_graph_run.py tests/test_cli.py tests/test_langgraph_studio.py
```

- [ ] **Step 3: Run full test suite**

Run:

```batch
uv run pytest -q
```

Expected:

- all tests pass without requiring a live Claude configuration

## Task 7: Manual Validation

- [ ] **Step 1: Validate fallback mode without `.env`**

Run the CLI demo with no `.env` or Claude disabled and confirm:

- the workflow completes
- a deterministic design brief is still produced
- trace shows fallback metadata if enabled by implementation

- [ ] **Step 2: Validate Claude-backed mode with `.env`**

Create a local `.env` and confirm:

- the worker uses Claude
- the result is still a valid `design_brief`
- the reviewer path still completes normally

- [ ] **Step 3: Optional Studio validation**

Run `langgraph dev` and confirm the graph continues to execute and surface worker results correctly in Studio.

## Self-Review Checklist

- [ ] no hidden dependency on system-wide environment variables
- [ ] `.env.example` matches README documentation
- [ ] tests do not require live network or real Claude credentials
- [ ] worker output contract remains compatible with current reviewer and artifact registry logic
- [ ] fallback behavior is explicit in both code and trace output
