from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import typer

from studio.agents.profile_loader import AgentProfileLoader
from studio.agents.profile_schema import AgentProfileError
from studio.domain.approvals import approve_design_doc
from studio.domain.requirement_flow import transition_requirement
from studio.domain.services import validate_requirement_ready_for_dev
from studio.llm import ClaudeRoleAdapter, ClaudeRoleError
from studio.runtime.graph import build_demo_runtime, build_meeting_graph
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.balance_table import BalanceTable
from studio.schemas.requirement import RequirementCard, RequirementStatus
from studio.storage.workspace import StudioWorkspace

app = typer.Typer(help="Game Studio Runtime Kernel CLI.")
requirement_app = typer.Typer(help="Requirement commands.")
design_app = typer.Typer(help="Design review commands.")
workflow_app = typer.Typer(help="Workflow execution commands.")
agent_app = typer.Typer(help="Direct agent debugging commands.")

app.add_typer(requirement_app, name="requirement")
app.add_typer(design_app, name="design")
app.add_typer(workflow_app, name="workflow")
app.add_typer(agent_app, name="agent")

project_app = typer.Typer(help="Project management commands")
app.add_typer(project_app, name="project")


def _workspace_store(workspace: Path) -> StudioWorkspace:
    store = StudioWorkspace(workspace / ".studio-data")
    store.ensure_layout()
    return store


def _fail_cli(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _next_id(root: Path, prefix: str) -> str:
    for _ in range(32):
        candidate = f"{prefix}_{uuid4().hex[:8]}"
        if not (root / f"{candidate}.json").exists():
            return candidate
    _fail_cli(f"failed to allocate a unique '{prefix}' id after repeated collisions")


def _normalize_demo_result(result: object) -> dict[str, object]:
    if isinstance(result, dict):
        return dict(result)
    return {"result": result}


def _load_requirement(store: StudioWorkspace, requirement_id: str) -> RequirementCard:
    try:
        return store.requirements.get(requirement_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        _fail_cli(f"could not load requirement '{requirement_id}'")


def _load_design_doc(store: StudioWorkspace, design_doc_id: str) -> DesignDoc:
    try:
        return store.design_docs.get(design_doc_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        _fail_cli(f"could not load design doc '{design_doc_id}'")


def _load_linked_design_doc(store: StudioWorkspace, requirement: RequirementCard) -> DesignDoc:
    if not requirement.design_doc_id:
        _fail_cli(f"requirement '{requirement.id}' has no design doc")
    return _load_design_doc(store, requirement.design_doc_id)


def _load_linked_balance_tables(
    store: StudioWorkspace,
    requirement: RequirementCard,
) -> list[BalanceTable]:
    tables: list[BalanceTable] = []
    for balance_table_id in requirement.balance_table_ids:
        try:
            tables.append(store.balance_tables.get(balance_table_id))
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            _fail_cli(f"could not load balance table '{balance_table_id}'")
    return tables


def _transition_requirement(
    requirement: RequirementCard,
    next_status: RequirementStatus,
) -> RequirementCard:
    try:
        return transition_requirement(requirement, next_status)
    except ValueError as exc:
        _fail_cli(str(exc))


def _update_requirement_design_doc(
    requirement: RequirementCard,
    design_doc_id: str,
) -> RequirementCard:
    return requirement.model_copy(update={"design_doc_id": design_doc_id})


def _append_requirement_bug(requirement: RequirementCard, bug_id: str) -> RequirementCard:
    return requirement.model_copy(update={"bug_ids": [*requirement.bug_ids, bug_id]})


def _payload_to_data(payload: object) -> object:
    if hasattr(payload, "model_dump") and callable(payload.model_dump):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "__dict__") and payload.__dict__:
        return payload.__dict__

    public_attrs: dict[str, object] = {}
    for name in dir(payload):
        if name.startswith("_"):
            continue
        value = getattr(payload, name)
        if callable(value):
            continue
        public_attrs[name] = value
    if public_attrs:
        return public_attrs
    return str(payload)


def _echo_agent_reply(payload: object) -> None:
    if isinstance(payload, str):
        typer.echo(payload)
        return
    typer.echo(json.dumps(_payload_to_data(payload), indent=2, ensure_ascii=False, default=str))


def _profile_path(loader: AgentProfileLoader, agent_name: str) -> Path:
    repo_root = getattr(loader, "repo_root", Path(__file__).resolve().parents[2])
    return Path(repo_root) / "studio" / "agents" / "profiles" / f"{agent_name}.yaml"


def _run_agent_chat_once(agent_name: str, message: str, profile: object) -> object:
    runner = ClaudeRoleAdapter(profile=profile)
    return runner.chat(message)


@app.callback()
def _main() -> None:
    """Game studio runtime commands."""


@project_app.command("kickoff")
def project_kickoff(
    workspace: Path = typer.Option(..., "--workspace", "-w", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement to kick off"),
    user_intent: str | None = typer.Option(None, "--user-intent", help="Override user intent"),
) -> None:
    import uuid

    from studio.storage.session_registry import SessionRegistry
    from studio.storage.workspace import StudioWorkspace

    ws_root = workspace / ".studio-data"
    ws = StudioWorkspace(ws_root)
    requirement = _load_requirement(ws, requirement_id)
    intent = user_intent or requirement.title
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    managed_agents = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
    registry = SessionRegistry(ws_root)
    registry.create_all(project_id, requirement_id, managed_agents)
    project_root = str(Path(__file__).resolve().parents[2])
    graph = build_meeting_graph()
    graph.invoke({
        "workspace_root": str(ws_root),
        "project_root": project_root,
        "requirement_id": requirement_id,
        "user_intent": intent,
        "project_id": project_id,
    })
    typer.echo(f"{project_id} kickoff_complete")


@app.command("run-demo")
def run_demo(
    workspace: Path = typer.Option(..., "--workspace", "-w", help="Directory for artifacts, memory, checkpoints"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Goal prompt for the demo graph"),
    require_approval: bool = typer.Option(False, "--require-approval", help="Pause with a human gate in output"),
) -> None:
    runtime = build_demo_runtime(workspace)
    result = _normalize_demo_result(runtime.invoke({"prompt": prompt}))
    if require_approval:
        telemetry = result.get("telemetry")
        if not isinstance(telemetry, dict):
            telemetry = {}
        result["human_gates"] = [
            {"gate_id": "approval-001", "reason": "final approval", "status": "pending"}
        ]
        telemetry["status"] = "awaiting_approval"
        result["telemetry"] = telemetry
    typer.echo(json.dumps(result, indent=2, default=str))


@requirement_app.command("create")
def create_requirement(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    title: str = typer.Option(..., "--title", help="Requirement title"),
) -> None:
    store = _workspace_store(workspace)
    requirement = RequirementCard(
        id=_next_id(store.requirements.root, "req"),
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
    requirement = _load_requirement(store, requirement_id)
    pending_review = _transition_requirement(
        _transition_requirement(requirement, "designing"),
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
    updated_requirement = _update_requirement_design_doc(pending_review, design_doc.id)
    store.design_docs.save(design_doc)
    store.requirements.save(updated_requirement)
    typer.echo(f"{design_doc.id} {design_doc.status}")


@design_app.command("approve")
def approve_design(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = _load_requirement(store, requirement_id)
    design_doc = _load_linked_design_doc(store, requirement)
    balance_tables = _load_linked_balance_tables(store, requirement)
    try:
        updated_doc, updated_requirement, logs = approve_design_doc(
            requirement,
            design_doc,
            balance_tables,
        )
    except ValueError as exc:
        _fail_cli(str(exc))
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
    requirement = _load_requirement(store, requirement_id)
    design_doc = _load_linked_design_doc(store, requirement)
    balance_tables = _load_linked_balance_tables(store, requirement)
    try:
        validate_requirement_ready_for_dev(requirement, design_doc, balance_tables)
    except ValueError as exc:
        _fail_cli(str(exc))
    self_test_passed = _transition_requirement(
        _transition_requirement(requirement, "implementing"),
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
    requirement = _load_requirement(store, requirement_id)
    testing = _transition_requirement(requirement, "testing")
    if not fail:
        accepted = _transition_requirement(testing, "pending_user_acceptance")
        store.requirements.save(accepted)
        typer.echo(f"{accepted.id} {accepted.status}")
        return

    implementing = _transition_requirement(testing, "implementing")
    bug = BugCard(
        id=_next_id(store.bugs.root, "bug"),
        requirement_id=requirement_id,
        title=f"QA failure for {requirement_id}",
        severity="high",
        owner="qa_agent",
        repro_steps=["generated by qa"],
    )
    updated_requirement = _append_requirement_bug(implementing, bug.id)
    store.bugs.save(bug)
    store.requirements.save(updated_requirement)
    typer.echo(f"{bug.id} {updated_requirement.status}")


@workflow_app.command("run-quality")
def run_quality(
    workspace: Path = typer.Option(..., "--workspace", help="Workspace root directory"),
    requirement_id: str = typer.Option(..., "--requirement-id", help="Requirement identifier"),
) -> None:
    store = _workspace_store(workspace)
    requirement = _load_requirement(store, requirement_id)
    done = _transition_requirement(
        _transition_requirement(requirement, "quality_check"),
        "done",
    )
    store.requirements.save(done)
    typer.echo(f"{done.id} {done.status}")


@agent_app.command("chat")
def agent_chat(
    agent: str = typer.Option(..., "--agent", help="Managed agent profile name"),
    message: str | None = typer.Option(None, "--message", help="Single-turn user message"),
    interactive: bool = typer.Option(False, "--interactive", help="Start a simple REPL"),
    verbose: bool = typer.Option(False, "--verbose", help="Print debug metadata before the reply"),
    project_id: str | None = typer.Option(None, "--project-id", help="Use project agent session"),
    workspace: Path | None = typer.Option(None, "--workspace", help="Workspace root (required with --project-id)"),
) -> None:
    if not interactive and not message:
        _fail_cli("--message is required unless --interactive is set")

    try:
        loader = AgentProfileLoader()
        profile = loader.load(agent)
    except AgentProfileError as exc:
        _fail_cli(str(exc))

    if project_id and not workspace:
        _fail_cli("--workspace is required when --project-id is set")

    session_id: str | None = None
    if project_id:
        from studio.storage.session_registry import SessionRegistry

        ws_root = workspace / ".studio-data"
        registry = SessionRegistry(ws_root)
        record = registry.find(project_id, agent)
        if record is None:
            _fail_cli(f"project agent session not found: {project_id}/{agent}")
        session_id = record.session_id
        registry.touch(project_id, agent)

    if verbose:
        debug_info = {
            "agent": agent,
            "profile_path": str(_profile_path(loader, agent)),
            "claude_project_root": str(profile.claude_project_root),
            "system_prompt": profile.system_prompt,
        }
        if session_id:
            debug_info["project_id"] = project_id
            debug_info["session_id"] = session_id
        typer.echo(json.dumps(debug_info, indent=2, ensure_ascii=False))

    try:
        if interactive:
            runner = ClaudeRoleAdapter(profile=profile, session_id=session_id)
            while True:
                user_input = typer.prompt(f"{agent}>")
                if user_input.strip().lower() in {"exit", "quit"}:
                    return
                _echo_agent_reply(runner.chat(user_input))
            return

        runner = ClaudeRoleAdapter(profile=profile, session_id=session_id)
        _echo_agent_reply(runner.chat(message or ""))
    except ClaudeRoleError as exc:
        _fail_cli(str(exc))


if __name__ == "__main__":
    app()
