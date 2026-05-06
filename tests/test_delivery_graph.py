from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

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
    for agent in ("art", "dev"):
        ws.sessions.save(
            ProjectAgentSession(
                project_id="proj_001",
                requirement_id="req_001",
                agent=agent,
                session_id=f"sess_{agent}",
            )
        )

    plan = DeliveryPlan(
        id="plan_001",
        meeting_id="meet_001",
        requirement_id="req_001",
        project_id="proj_001",
        status="active",
        task_ids=["task_art", "task_dev"],
        decision_gate_id="gate_001",
        decision_resolution_version=1,
    )
    ws.delivery_plans.save(plan)
    ws.decision_gates.save(
        KickoffDecisionGate(
            id="gate_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="resolved",
            resolution_version=1,
            items=[
                GateItem(
                    id="ui",
                    question="Choose UI style",
                    context="Pixel or minimal",
                    options=["pixel", "minimal"],
                    resolution="pixel",
                )
            ],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_art",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Write art guide",
            description="Create pixel art specs",
            owner_agent="art",
            status="ready",
            acceptance_criteria=["Guide exists"],
            decision_resolution_version=1,
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_dev",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement game UI",
            description="Use the art guide",
            owner_agent="dev",
            status="blocked",
            depends_on_task_ids=["task_art"],
            acceptance_criteria=["UI follows art guide"],
            decision_resolution_version=1,
        )
    )
    return plan.id


def test_delivery_graph_runs_dependency_batches_and_injects_context(
    tmp_path: Path, monkeypatch,
) -> None:
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    projects_root = tmp_path / "external-projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))
    plan_id = _seed_delivery_plan(workspace_root)
    calls: list[tuple[str, dict[str, object]]] = []

    class _Agent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state, **kwargs):
            calls.append((self.role, state.goal))
            project_dir = Path(str(state.goal["project_dir"]))
            if self.role == "art":
                (project_dir / "art").mkdir(parents=True, exist_ok=True)
                (project_dir / "art" / "ART_GUIDE.md").write_text(
                    "# Art Guide\n\nUse pixel art.",
                    encoding="utf-8",
                )
            else:
                (project_dir / "game").mkdir(parents=True, exist_ok=True)
                (project_dir / "game" / "index.html").write_text(
                    "<canvas></canvas>",
                    encoding="utf-8",
                )
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={
                    "plan": {"current_node": self.role},
                    "telemetry": {
                        f"{self.role}_report": {
                            "summary": f"{self.role} done",
                            "changes": [],
                            "checks": [],
                            "follow_ups": [],
                        }
                    },
                },
                trace={"node": self.role, "fallback_used": False},
            )

    class _Dispatcher:
        def __init__(self) -> None:
            self._agents = {"art": _Agent("art"), "dev": _Agent("dev")}

        def get(self, node_name: str):
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)

    result = build_delivery_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
            "plan_id": plan_id,
        }
    )

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "completed"
    assert ws.delivery_plans.get(plan_id).status == "completed"
    assert [role for role, _ in calls] == ["art", "dev"]
    assert calls[0][1]["resolved_decisions"] == [
        {
            "id": "ui",
            "question": "Choose UI style",
            "resolution": "pixel",
        }
    ]
    assert calls[1][1]["dependency_results"][0]["task_id"] == "task_art"
    assert "art/ART_GUIDE.md" in calls[1][1]["dependency_artifact_files"]
    assert calls[0][1]["project_dir"] == str(projects_root / "proj_001")
    assert ws.execution_results.get("result_task_art").changed_files == ["art/ART_GUIDE.md"]
    assert ws.execution_results.get("result_task_dev").changed_files == ["game/index.html"]


def test_delivery_graph_workspace_stub_agents_record_context(tmp_path: Path) -> None:
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    workspace_root.mkdir(parents=True)
    (workspace_root / "e2e_stub_delivery_agents").write_text("true", encoding="utf-8")
    plan_id = _seed_delivery_plan(workspace_root)

    result = build_delivery_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
            "plan_id": plan_id,
        }
    )

    ws = StudioWorkspace(workspace_root)
    project_dir = project_root.parent / "GS_projects" / "proj_001"
    dev_context = (project_dir / "debug" / "dev-context.json").read_text(encoding="utf-8")

    assert result["runner_status"] == "completed"
    assert ws.delivery_tasks.get("task_art").status == "done"
    assert ws.delivery_tasks.get("task_dev").status == "done"
    assert "art/ART_GUIDE.md" in dev_context
    assert "pixel" in dev_context


def test_delivery_graph_submits_agent_tasks_to_shared_pool(
    tmp_path: Path, monkeypatch,
) -> None:
    import studio.runtime.graph as graph_module

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_delivery_plan(workspace_root)
    submitted: list[tuple[str, str, str]] = []

    class _Agent:
        def __init__(self, role: str) -> None:
            self.role = role

        def run(self, state, **kwargs):
            project_dir = Path(str(state.goal["project_dir"]))
            if self.role == "art":
                (project_dir / "art").mkdir(parents=True, exist_ok=True)
                (project_dir / "art" / "ART_GUIDE.md").write_text(
                    "# Art Guide\n\nUse pixel art.",
                    encoding="utf-8",
                )
            else:
                (project_dir / "game").mkdir(parents=True, exist_ok=True)
                (project_dir / "game" / "index.html").write_text(
                    "<canvas></canvas>",
                    encoding="utf-8",
                )
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={
                    "telemetry": {
                        f"{self.role}_report": {
                            "summary": f"{self.role} done",
                            "changes": [],
                            "checks": [],
                            "follow_ups": [],
                        }
                    },
                },
                trace={"node": self.role, "fallback_used": False},
            )

    class _Dispatcher:
        def get(self, node_name: str):
            return _Agent(node_name)

    def _submit_agent(agent_type, requirement_id, requirement_title, fn, /, *args, **kwargs):
        submitted.append((agent_type, requirement_id, requirement_title))
        future: Future[object] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)
    monkeypatch.setattr(
        graph_module,
        "agent_pool",
        SimpleNamespace(submit_agent=_submit_agent),
        raising=False,
    )

    result = graph_module.build_delivery_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
            "plan_id": plan_id,
        }
    )

    assert result["runner_status"] == "completed"
    assert submitted == [
        ("art", "req_001", "Write art guide"),
        ("dev", "req_001", "Implement game UI"),
    ]


def test_delivery_graph_marks_failed_task_and_releases_lease(
    tmp_path: Path, monkeypatch,
) -> None:
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_delivery_plan(workspace_root)

    class _Agent:
        def run(self, state, **kwargs):
            raise RuntimeError("claude crashed")

    class _Dispatcher:
        def get(self, node_name: str):
            return _Agent()

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _Dispatcher)

    result = build_delivery_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(project_root),
            "plan_id": plan_id,
        }
    )

    ws = StudioWorkspace(workspace_root)
    task = ws.delivery_tasks.get("task_art")
    lease = ws.session_leases.get("proj_001_art")
    execution_result = ws.execution_results.get(task.execution_result_id)

    assert result["runner_status"] == "failed"
    assert result["failed_task_ids"] == ["task_art"]
    assert task.status == "failed"
    assert task.last_error == "claude crashed"
    assert task.attempt_count == 1
    assert lease.status == "released"
    assert execution_result.error_message == "claude crashed"
    assert execution_result.exception_type == "RuntimeError"
