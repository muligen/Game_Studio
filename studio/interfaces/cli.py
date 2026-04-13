from __future__ import annotations

import json
from pathlib import Path

import typer

from studio.runtime.graph import build_demo_runtime

app = typer.Typer(help="Game Studio Runtime Kernel CLI.")


@app.callback()
def _main() -> None:
    """Game studio runtime commands."""


@app.command("run-demo")
def run_demo(
    workspace: Path = typer.Option(..., "--workspace", "-w", help="Directory for artifacts, memory, checkpoints"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Goal prompt for the demo graph"),
    require_approval: bool = typer.Option(False, "--require-approval", help="Pause with a human gate in output"),
) -> None:
    runtime = build_demo_runtime(workspace)
    result = runtime.invoke({"prompt": prompt})
    if require_approval:
        result["human_gates"] = [
            {"gate_id": "approval-001", "reason": "final approval", "status": "pending"}
        ]
        result["telemetry"]["status"] = "awaiting_approval"
    typer.echo(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    app()
