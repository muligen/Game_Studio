from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app


def test_run_demo_command_outputs_completion_status(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-demo",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Design a simple 2D game concept",
        ],
    )

    assert result.exit_code == 0
    assert '"status": "completed"' in result.stdout
