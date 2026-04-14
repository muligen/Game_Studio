# Game Studio Runtime Kernel

Initial LangGraph runtime kernel for orchestrating multi-agent game production workflows.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed

## Development

Install dependencies and the project into a local `.venv` (dev group included by default):

```batch
uv sync
```

Run tests:

```batch
uv run pytest -v
```

## Demo

```batch
uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

Or after `uv sync`, activate `.venv` and use `python` as usual:

```batch
.venv\Scripts\activate
python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

## Claude Worker

The `worker` node can optionally use Claude Agent SDK to generate the `design_brief` artifact. Configuration is read from a project-root `.env` file only.

Start from [.env.example](/f:/projs/Game_Studio/.env.example):

```env
GAME_STUDIO_CLAUDE_ENABLED=false
GAME_STUDIO_CLAUDE_MODE=text
GAME_STUDIO_CLAUDE_MODEL=
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
```

Recommended flow:

1. Copy `.env.example` to `.env`
2. Set `GAME_STUDIO_CLAUDE_ENABLED=true`
3. Fill `ANTHROPIC_API_KEY`
4. Optionally set `ANTHROPIC_BASE_URL` if you use a proxy or compatible gateway
5. Run the demo CLI

Example:

```batch
uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

Behavior notes:

- If Claude is disabled, the worker uses the built-in deterministic fallback artifact
- If `.env` is incomplete or Claude invocation fails, the graph still completes with fallback output
- The worker trace includes fallback metadata so you can see whether Claude or fallback was used
- Live Claude execution requires both the Python package dependency and a working Claude Code installation available to the SDK

## LangGraph Studio

This repository now exposes the demo runtime through `langgraph dev` so you can inspect the graph locally in LangGraph Studio.

### Prerequisites

- `langgraph-cli` installed locally, or use `uvx`

Example with `uvx`:

```batch
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev
```

On Windows PowerShell, set UTF-8 output first if the CLI prints encoding errors:

```powershell
$env:PYTHONUTF8 = "1"
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev
```

If you have the CLI installed already:

```batch
langgraph dev
```

You can also verify the config before launching Studio:

```powershell
$env:PYTHONUTF8 = "1"
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph validate
```

The repository root includes [langgraph.json](/f:/projs/Game_Studio/langgraph.json), which points LangGraph at the Studio adapter in [studio/langgraph_app.py](/f:/projs/Game_Studio/studio/langgraph_app.py).

### What It Loads

- Graph id: `game_studio_demo`
- Entry module: [studio/langgraph_app.py](/f:/projs/Game_Studio/studio/langgraph_app.py)
- Default workspace: `.runtime-data/langgraph-dev`

Studio-triggered runs write artifacts, memory, and checkpoints under `.runtime-data/langgraph-dev`.

### Optional LangSmith Tracing

Local Studio visualization works without LangSmith credentials. If you want traces to also appear in LangSmith, set these environment variables before running `langgraph dev`:

```batch
set LANGSMITH_TRACING=true
set LANGSMITH_API_KEY=your_api_key
set LANGSMITH_PROJECT=game-studio-runtime
```

On PowerShell:

```powershell
$env:LANGSMITH_TRACING = "true"
$env:LANGSMITH_API_KEY = "your_api_key"
$env:LANGSMITH_PROJECT = "game-studio-runtime"
langgraph dev
```

### Manual Verification

1. Start the local LangGraph server with `langgraph dev` or the `uvx` command above.
2. Open the Studio URL shown by the CLI.
3. Run the `game_studio_demo` graph with input such as `{"prompt": "Design a simple 2D game concept"}`.
4. Confirm Studio shows the `planner -> worker -> reviewer` flow and the run completes successfully.
