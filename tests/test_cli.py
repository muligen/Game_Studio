import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app

_REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_run_demo_via_python_module_emits_json(tmp_path: Path) -> None:
    """Regression: `python -m studio.interfaces.cli` must call Typer (see cli __main__ guard)."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "studio.interfaces.cli",
            "run-demo",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Design a simple 2D game concept",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "expected JSON on stdout"
    assert '"status": "completed"' in proc.stdout
