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
