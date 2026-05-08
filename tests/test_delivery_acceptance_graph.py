from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import Future

from studio.schemas.acceptance import AcceptanceRun, AcceptanceCriterionResult
from studio.runtime.acceptance_verifier import VerificationResult
from studio.schemas.delivery import DeliveryPlan, DeliveryTask, GateItem, KickoffDecisionGate
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.schemas.runtime import NodeDecision, NodeResult
from studio.schemas.session import ProjectAgentSession
from studio.storage.workspace import StudioWorkspace


def _seed_delivery_plan(workspace_root: Path) -> str:
    ws = StudioWorkspace(workspace_root)
    ws.ensure_layout()
    ws.requirements.save(RequirementCard(id="req_001", title="Snake MVP", status="approved"))
    ws.meetings.save(
        MeetingMinutes(
            id="meet_001",
            requirement_id="req_001",
            title="Snake Kickoff",
            status="completed",
            decisions=["Build a browser snake MVP"],
            consensus_points=["Use web delivery"],
        )
    )
    ws.sessions.save(
        ProjectAgentSession(
            project_id="proj_001",
            requirement_id="req_001",
            agent="dev",
            session_id="sess_dev",
        )
    )
    plan = DeliveryPlan(
        id="plan_001",
        meeting_id="meet_001",
        requirement_id="req_001",
        project_id="proj_001",
        status="active",
        task_ids=["task_dev"],
    )
    ws.delivery_plans.save(plan)
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_dev",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement game",
            description="Build the snake game",
            owner_agent="dev",
            status="ready",
            acceptance_criteria=["Game works"],
        )
    )
    return plan.id


def _make_agent():
    class _Agent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state, **kwargs):
            project_dir = Path(str(state.goal["project_dir"]))
            (project_dir / "game").mkdir(parents=True, exist_ok=True)
            (project_dir / "game" / "index.html").write_text(
                "<canvas></canvas>", encoding="utf-8",
            )
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={
                    "telemetry": {
                        f"{self.role}_report": {
                            "summary": f"{self.role} done",
                            "changes": [],
                            "checks": ["stub check"],
                            "follow_ups": [],
                        }
                    },
                },
                trace={"node": self.role, "fallback_used": False},
            )

    return _Agent


def test_acceptance_passes_on_first_try(tmp_path: Path, monkeypatch) -> None:
    import studio.runtime.graph as graph_module
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    plan_id = _seed_delivery_plan(workspace_root)

    class _Dispatcher:
        def get(self, node_name: str):
            return _make_agent()(node_name)

    def _submit(agent_type, req_id, title, fn, /, *args, **kwargs):
        future: Future[object] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)
    graph_module.agent_pool = SimpleNamespace(submit_agent=_submit)

    def _fake_verify(project_dir, *, artifacts_root, run_id):
        return VerificationResult(startup_ok=True, browser_ok=True, evidence=[])
    monkeypatch.setattr("studio.runtime.acceptance_verifier.verify_project", _fake_verify)

    def _fake_evaluate(*, contract, verification, task_results, run_id, attempt_number):
        return AcceptanceRun(
            id=run_id,
            contract_id=contract.id,
            plan_id=contract.plan_id,
            requirement_id=contract.requirement_id,
            project_id=contract.project_id,
            attempt_number=attempt_number,
            status="passed",
            criteria_results=[],
        )
    monkeypatch.setattr("studio.runtime.acceptance_evaluator.evaluate_acceptance", _fake_evaluate)

    result = build_delivery_graph().invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(tmp_path),
        "plan_id": plan_id,
    })

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "accepted"
    assert ws.delivery_plans.get(plan_id).status == "accepted"
    assert ws.requirements.get("req_001").status == "done"


def test_acceptance_fails_then_repairs_and_passes(tmp_path: Path, monkeypatch) -> None:
    import studio.runtime.graph as graph_module
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    plan_id = _seed_delivery_plan(workspace_root)

    call_count = {"evaluate": 0}

    class _Dispatcher:
        def get(self, node_name: str):
            return _make_agent()(node_name)

    def _submit(agent_type, req_id, title, fn, /, *args, **kwargs):
        future: Future[object] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)
    graph_module.agent_pool = SimpleNamespace(submit_agent=_submit)

    def _fake_verify(project_dir, *, artifacts_root, run_id):
        return VerificationResult(startup_ok=True, browser_ok=True, evidence=[])
    monkeypatch.setattr("studio.runtime.acceptance_verifier.verify_project", _fake_verify)

    def _fake_evaluate(*, contract, verification, task_results, run_id, attempt_number):
        call_count["evaluate"] += 1
        if attempt_number == 1:
            return AcceptanceRun(
                id=run_id,
                contract_id=contract.id,
                plan_id=contract.plan_id,
                requirement_id=contract.requirement_id,
                project_id=contract.project_id,
                attempt_number=attempt_number,
                status="failed",
                criteria_results=[
                    AcceptanceCriterionResult(
                        criterion_id="crit_001",
                        status="failed",
                        evidence_ids=[],
                        reason="Page is blank",
                        repair_hint="Add visible game surface",
                        owner_hint="dev",
                        blocking=True,
                    ),
                ],
            )
        return AcceptanceRun(
            id=run_id,
            contract_id=contract.id,
            plan_id=contract.plan_id,
            requirement_id=contract.requirement_id,
            project_id=contract.project_id,
            attempt_number=attempt_number,
            status="passed",
            criteria_results=[],
        )
    monkeypatch.setattr("studio.runtime.acceptance_evaluator.evaluate_acceptance", _fake_evaluate)

    result = build_delivery_graph().invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(tmp_path),
        "plan_id": plan_id,
    })

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "accepted"
    assert ws.delivery_plans.get(plan_id).status == "accepted"
    assert ws.requirements.get("req_001").status == "done"
    assert call_count["evaluate"] == 2

    bug_tasks = [t for t in ws.delivery_tasks.list_all() if t.kind == "bug_fix"]
    assert len(bug_tasks) == 1
    assert bug_tasks[0].status == "done"
    assert "visible game surface" in bug_tasks[0].title.lower() or "Fix:" in bug_tasks[0].title


def test_acceptance_hits_max_attempts_and_stops(tmp_path: Path, monkeypatch) -> None:
    import studio.runtime.graph as graph_module
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    plan_id = _seed_delivery_plan(workspace_root)

    class _Dispatcher:
        def get(self, node_name: str):
            return _make_agent()(node_name)

    def _submit(agent_type, req_id, title, fn, /, *args, **kwargs):
        future: Future[object] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)
    graph_module.agent_pool = SimpleNamespace(submit_agent=_submit)

    def _fake_verify(project_dir, *, artifacts_root, run_id):
        return VerificationResult(startup_ok=True, browser_ok=True, evidence=[])
    monkeypatch.setattr("studio.runtime.acceptance_verifier.verify_project", _fake_verify)

    def _always_fails(*, contract, verification, task_results, run_id, attempt_number):
        return AcceptanceRun(
            id=run_id,
            contract_id=contract.id,
            plan_id=contract.plan_id,
            requirement_id=contract.requirement_id,
            project_id=contract.project_id,
            attempt_number=attempt_number,
            status="failed",
            criteria_results=[
                AcceptanceCriterionResult(
                    criterion_id="crit_001",
                    status="failed",
                    evidence_ids=[],
                    reason="Unfixable problem",
                    repair_hint="Give up",
                    owner_hint="dev",
                    blocking=True,
                ),
            ],
        )
    monkeypatch.setattr("studio.runtime.acceptance_evaluator.evaluate_acceptance", _always_fails)

    result = build_delivery_graph().invoke({
        "workspace_root": str(workspace_root),
        "project_root": str(tmp_path),
        "plan_id": plan_id,
    })

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "needs_attention"
    assert ws.delivery_plans.get(plan_id).status == "needs_attention"
    assert result["acceptance_attempt"] == 3
    assert ws.requirements.get("req_001").status != "done"
