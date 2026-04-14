from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app


def test_requirement_create_and_list(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        [
            "requirement",
            "create",
            "--workspace",
            str(tmp_path),
            "--title",
            "Add relic system",
        ],
    )
    assert create_result.exit_code == 0
    assert "req_" in create_result.stdout

    list_result = runner.invoke(app, ["requirement", "list", "--workspace", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "Add relic system" in list_result.stdout


def test_workflow_run_design_creates_design_doc(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]

    result = runner.invoke(
        app,
        ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )
    assert result.exit_code == 0
    assert "design_" in result.stdout


def test_design_approve_moves_requirement_to_approved(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    result = runner.invoke(app, ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", "req_001"])
    assert result.exit_code == 0
    assert "approved" in result.stdout


def test_workflow_run_dev_and_qa_generates_bug_on_failure(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    runner.invoke(app, ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    runner.invoke(app, ["workflow", "run-dev", "--workspace", str(tmp_path), "--requirement-id", requirement_id])

    result = runner.invoke(
        app,
        ["workflow", "run-qa", "--workspace", str(tmp_path), "--requirement-id", requirement_id, "--fail"],
    )
    assert result.exit_code == 0
    assert "bug_" in result.stdout
