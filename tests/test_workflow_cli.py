from pathlib import Path

from typer.testing import CliRunner

from studio.interfaces.cli import app
from studio.storage.workspace import StudioWorkspace


def _workspace(tmp_path: Path) -> StudioWorkspace:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    workspace.ensure_layout()
    return workspace


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
    requirement_id = create_result.stdout.strip().split()[0]

    requirement = _workspace(tmp_path).requirements.get(requirement_id)
    assert requirement.title == "Add relic system"
    assert requirement.status == "draft"
    assert requirement.design_doc_id is None
    assert requirement.bug_ids == []

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

    workspace = _workspace(tmp_path)
    requirement = workspace.requirements.get(requirement_id)
    design_doc_id = result.stdout.strip().split()[0]
    design_doc = workspace.design_docs.get(design_doc_id)

    assert requirement.status == "pending_user_review"
    assert requirement.design_doc_id == design_doc_id
    assert design_doc.requirement_id == requirement_id
    assert design_doc.status == "pending_user_review"


def test_design_approve_moves_requirement_to_approved(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])
    result = runner.invoke(
        app,
        ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )
    assert result.exit_code == 0
    assert "approved" in result.stdout

    workspace = _workspace(tmp_path)
    requirement = workspace.requirements.get(requirement_id)
    design_doc = workspace.design_docs.get(requirement.design_doc_id or "")

    assert requirement.status == "approved"
    assert design_doc.status == "approved"
    assert requirement.design_doc_id == design_doc.id
    assert len(workspace.logs.list_all()) == 1
    assert workspace.logs.list_all()[0].target_id == design_doc.id


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

    workspace = _workspace(tmp_path)
    requirement = workspace.requirements.get(requirement_id)
    bug_id = result.stdout.strip().split()[0]
    bug = workspace.bugs.get(bug_id)

    assert requirement.status == "implementing"
    assert requirement.design_doc_id is not None
    assert requirement.bug_ids == [bug_id]
    assert bug.requirement_id == requirement_id
    assert bug.status == "new"


def test_design_approve_without_design_doc_fails_cleanly(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]

    result = runner.invoke(
        app,
        ["design", "approve", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )

    assert result.exit_code != 0
    assert "has no design doc" in result.stdout


def test_workflow_run_dev_with_missing_design_doc_file_fails_cleanly(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    design_result = runner.invoke(
        app,
        ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )
    design_doc_id = design_result.stdout.strip().split()[0]
    (_workspace(tmp_path).design_docs.root / f"{design_doc_id}.json").unlink()

    result = runner.invoke(
        app,
        ["workflow", "run-dev", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )

    assert result.exit_code != 0
    assert f"could not load design doc '{design_doc_id}'" in result.stdout


def test_workflow_run_dev_before_approval_fails_cleanly(tmp_path: Path) -> None:
    runner = CliRunner()
    create_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Add relic system"],
    )
    requirement_id = create_result.stdout.strip().split()[0]
    runner.invoke(app, ["workflow", "run-design", "--workspace", str(tmp_path), "--requirement-id", requirement_id])

    result = runner.invoke(
        app,
        ["workflow", "run-dev", "--workspace", str(tmp_path), "--requirement-id", requirement_id],
    )

    assert result.exit_code != 0
    assert "design doc must be approved" in result.stdout


def test_requirement_ids_do_not_collide_after_deleted_record(tmp_path: Path) -> None:
    runner = CliRunner()
    first_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "First requirement"],
    )
    first_id = first_result.stdout.strip().split()[0]
    (_workspace(tmp_path).requirements.root / f"{first_id}.json").unlink()

    second_result = runner.invoke(
        app,
        ["requirement", "create", "--workspace", str(tmp_path), "--title", "Second requirement"],
    )
    second_id = second_result.stdout.strip().split()[0]

    assert second_result.exit_code == 0
    assert second_id != first_id
