# Game Studio Runtime Kernel

## Game Studio Runtime Kernel

Initial LangGraph runtime kernel for orchestrating multi-agent game production workflows.

## Development

```batch
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest -v
```

## Demo

```batch
python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```
