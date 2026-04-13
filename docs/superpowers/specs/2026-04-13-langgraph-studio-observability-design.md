# LangGraph Studio Observability Design

## Summary

This document defines a minimal observability integration for the Game Studio Runtime Kernel so the existing demo workflow can be loaded by `langgraph dev` and inspected in LangGraph Studio. The primary goal is local graph visualization and interactive execution of the current `planner -> worker -> reviewer` flow. Optional LangSmith tracing support will be documented, but cloud tracing is not required for the base path.

## Goals

- Make the existing demo graph discoverable by `langgraph dev`
- Allow LangGraph Studio to render the current runtime graph and execute it locally
- Preserve the existing CLI workflow without changing its behavior
- Keep filesystem-backed runtime data working during Studio runs
- Document an optional LangSmith tracing path for future observability upgrades

## Non-Goals

- Reorganizing the runtime into a new multi-graph architecture
- Replacing the current CLI entrypoint
- Making LangSmith tracing mandatory
- Adding new workflow nodes or changing runtime behavior
- Building custom Studio dashboards or advanced replay tooling

## Current Project Context

The repository already has a compiled demo runtime built in `studio/runtime/graph.py`. That runtime writes artifacts, memory entries, and checkpoints under a caller-provided workspace directory. The CLI entrypoint in `studio/interfaces/cli.py` passes a workspace explicitly, but `langgraph dev` needs a stable top-level graph entry that can be imported without CLI arguments.

This means the integration problem is mostly an adapter problem:

- expose a stable graph entry for local Agent Server discovery
- provide a default workspace for Studio-driven runs
- leave the current runtime implementation intact

## Recommended Approach

Use a thin LangGraph Studio adapter module plus a repository-level `langgraph.json`.

### Why this approach

- It is the smallest safe change that satisfies the local visualization goal
- It avoids unnecessary refactoring of the existing runtime layout
- It creates a clean seam between CLI concerns and Studio concerns
- It keeps future options open for a later `studio/graphs/` expansion

## Alternatives Considered

### Option 1: Thin adapter module and `langgraph.json` (recommended)

Create a dedicated module that imports `build_demo_runtime()` and instantiates the compiled graph with a default workspace under `.runtime-data/langgraph-dev`.

Trade-offs:

- Pros: minimal changes, fastest to validate, lowest regression risk
- Cons: multi-graph support is deferred to a later change

### Option 2: Restructure into a dedicated `studio/graphs/` package now

Move or wrap the current demo graph into a formal graph package and register it from there.

Trade-offs:

- Pros: cleaner long-term organization
- Cons: larger change surface, more churn in an early-stage runtime

### Option 3: Add mandatory LangSmith-first observability

Require tracing configuration and treat local visualization as part of a broader tracing integration.

Trade-offs:

- Pros: stronger observability story from day one
- Cons: unnecessary setup friction for the immediate goal and more external dependency on API credentials

## Architecture

The integration adds a single Studio-facing entrypoint while keeping the existing runtime untouched.

```text
langgraph dev
  -> langgraph.json
  -> studio/langgraph_app.py
  -> build_demo_runtime(default_workspace)
  -> compiled demo graph
  -> local execution in LangGraph Studio
```

### Components

#### 1. Studio Graph Adapter

Add a new module at `studio/langgraph_app.py`.

Responsibilities:

- define the default workspace path for Studio runs
- construct the compiled demo runtime graph
- expose a stable import target for `langgraph dev`

Design constraints:

- must be importable without CLI arguments
- must not mutate unrelated runtime behavior
- must keep setup logic simple and deterministic

#### 2. LangGraph Configuration File

Add `langgraph.json` at the repository root.

Responsibilities:

- point the local Agent Server at the Studio graph adapter
- describe how the graph should be discovered during `langgraph dev`
- optionally reference environment configuration if needed later

This file is the handshake between the repo and LangGraph Studio tooling.

#### 3. Documentation Updates

Update `README.md` with a dedicated local observability section.

Responsibilities:

- explain prerequisite installation for local Studio usage
- document how to run `langgraph dev`
- explain the default workspace location used during Studio runs
- document optional LangSmith tracing environment variables

## Default Workspace Strategy

Studio runs need a stable workspace because the current runtime persists artifacts, memory, and checkpoints to disk. The integration will use:

- `.runtime-data/langgraph-dev`

This path is repository-local, predictable, and separate from ad hoc CLI workspaces.

### Rationale

- easy to inspect after a Studio run
- no need for runtime parameters during graph import
- avoids mixing Studio data with arbitrary user-selected demo runs

## Data Flow

1. The developer starts `langgraph dev` from the repository root
2. The LangGraph local server reads `langgraph.json`
3. The server imports the Studio adapter module
4. The adapter builds the compiled demo runtime using the default workspace
5. Studio loads the graph and renders the current node topology
6. A user triggers a run with input state such as `{"prompt": "..."}`
7. The runtime executes the existing nodes and writes runtime data to `.runtime-data/langgraph-dev`
8. If tracing is enabled via environment variables, LangSmith receives traces in addition to local execution

## Error Handling

### Missing Workspace

The adapter should rely on the existing runtime behavior, which already creates needed storage directories when the graph is built or executed. No extra user step should be required.

### Missing LangSmith Credentials

Studio graph loading must still work when LangSmith credentials are absent. Optional tracing should remain opt-in and documentation-led rather than enforced in code.

### Import Stability

The Studio adapter must avoid side effects beyond graph construction so that `langgraph dev` can import it reliably.

## Testing Strategy

### Automated Validation

Add a test that imports the new Studio adapter module and confirms the exported graph can be invoked successfully with the existing demo input shape.

The test should verify:

- the module is importable
- a compiled graph object is exposed
- a run produces the expected final status

### Manual Validation

The README should include a short verification flow:

1. install any required LangGraph local tooling
2. run `langgraph dev`
3. open the local Studio URL
4. execute the demo graph with a prompt input
5. confirm the graph and state transitions are visible

## Files To Add Or Modify

Add:

- `studio/langgraph_app.py`
- `langgraph.json`
- `tests/test_langgraph_studio.py`

Modify:

- `README.md`

## Compatibility Notes

- The existing CLI remains the canonical demo runner for command-line use
- The Studio adapter is an additional entrypoint, not a replacement
- Optional LangSmith tracing configuration should be documented but not required for tests or local graph loading

## Success Criteria

This work is successful when:

- `langgraph dev` can discover the repository graph
- LangGraph Studio shows the current demo flow
- the graph can be executed from Studio with the same input shape used by the CLI
- existing CLI and test behavior remain intact
- the repository clearly documents how to use local Studio observability

## Final Recommendation

Implement Studio observability as a thin adapter over the existing demo runtime. Add a dedicated graph entry module, register it with `langgraph.json`, use a fixed local workspace at `.runtime-data/langgraph-dev`, and document optional LangSmith tracing separately from the base local visualization workflow.
