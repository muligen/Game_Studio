from __future__ import annotations

import json
from pathlib import Path

import typer

from studio.domain.approvals import approve_design_doc
from studio.domain.requirement_flow import transition_requirement
from studio.domain.services import validate_requirement_ready_for_dev
from studio.runtime.graph import build_demo_runtime
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace

app = typer.Typer(help="Game Studio Runtime Kernel CLI.")
requirement_app = typer.Typer(help="Requirement commands.")
design_app = typer.Typer(help="Design review commands.")
workflow_app = typer.Typer(help="Workflow execution commands.")

app.add_typer(requirement_app, name="requirement")
app.add_typer(design_app, name="design")
app.add_typer(workflow_app, name="workflow")


def _workspace_store(workspace: Path) -> StudioWorkspace:
    store = StudioWorkspace(workspace / ".studio-data")
    store.ensure_layout()
    return store


def _next_id(prefix: str, existing_count: int) -> str:
    return f"{prefix}_{existing_count + 1:03d}"


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


@requirement_app.command("create")
def create_requirement(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    title: str = typer.Option(..., "--title", help="Requirement title"),
) -> None:
    store = _workspace_store(workspace)
    requirement = RequirementCard(
        id=_next_id("req", len(store.requirements.list_all())),
        title=title,
    )
    store.requirements.save(requirement)
    typer.echo(f"{requirement.id} {requirement.title} {requirement.status}")


@requirement_app.command("list")
def list_requirements(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
) -> None:
    store = _workspace_store(workspace)
    for requirement in store.requirements.list_all():
        typer.echo(f"{requirement.id} {requirement.priority} {requirement.status} {requirement.title}")


@workflow_app.command("run-design")
def run_design(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = store.requirements.get(requirement_id)
    pending_review = transition_requirement(
        transition_requirement(requirement, "designing"),
        "pending_user_review",
    )
    design_doc = DesignDoc(
        id=f"design_{requirement.id.split('_')[-1]}",
        requirement_id=requirement.id,
        title=f"{requirement.title} Design",
        summary=requirement.title,
        core_rules=["rule 1"],
        acceptance_criteria=["criterion 1"],
        open_questions=["question 1"],
        status="pending_user_review",
    )
    updated_requirement = pending_review.model_copy(update={"design_doc_id": design_doc.id})
    store.design_docs.save(design_doc)
    store.requirements.save(updated_requirement)
    typer.echo(f"{design_doc.id} {design_doc.status}")


@design_app.command("approve")
def approve_design(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = store.requirements.get(requirement_id)
    design_doc = store.design_docs.get(requirement.design_doc_id or "")
    updated_doc, updated_requirement, logs = approve_design_doc(requirement, design_doc, [])
    store.design_docs.save(updated_doc)
    store.requirements.save(updated_requirement)
    for log in logs:
        store.logs.save(log)
    typer.echo(f"{updated_doc.id} {updated_doc.status} {updated_requirement.status}")


@workflow_app.command("run-dev")
def run_dev(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = store.requirements.get(requirement_id)
    design_doc = store.design_docs.get(requirement.design_doc_id or "")
    validate_requirement_ready_for_dev(requirement, design_doc, [])
    self_test_passed = transition_requirement(
        transition_requirement(requirement, "implementing"),
        "self_test_passed",
    )
    store.requirements.save(self_test_passed)
    typer.echo(f"{self_test_passed.id} {self_test_passed.status}")


@workflow_app.command("run-qa")
def run_qa(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
    fail: bool = typer.Option(False, "--fail", help="Create a bug and send the requirement back to implementing"),
) -> None:
    store = _workspace_store(workspace)
    requirement = store.requirements.get(requirement_id)
    testing = transition_requirement(requirement, "testing")
    if not fail:
        accepted = transition_requirement(testing, "pending_user_acceptance")
        store.requirements.save(accepted)
        typer.echo(f"{accepted.id} {accepted.status}")
        return

    implementing = transition_requirement(testing, "implementing")
    bug = BugCard(
        id=_next_id("bug", len(store.bugs.list_all())),
        requirement_id=requirement_id,
        title=f"QA failure for {requirement_id}",
        severity="high",
        owner="qa_agent",
        repro_steps=["generated by qa"],
    )
    updated_requirement = implementing.model_copy(
        update={"bug_ids": [*implementing.bug_ids, bug.id]}
    )
    store.bugs.save(bug)
    store.requirements.save(updated_requirement)
    typer.echo(f"{bug.id} {updated_requirement.status}")


@workflow_app.command("run-quality")
def run_quality(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = store.requirements.get(requirement_id)
    done = transition_requirement(
        transition_requirement(requirement, "quality_check"),
        "done",
    )
    store.requirements.save(done)
    typer.echo(f"{done.id} {done.status}")


if __name__ == "__main__":
    app()
