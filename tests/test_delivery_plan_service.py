"""Tests for studio.storage.delivery_plan_service.DeliveryPlanService."""

from __future__ import annotations

from pathlib import Path

import pytest

from studio.schemas.meeting import MeetingMinutes
from studio.schemas.session import ProjectAgentSession
from studio.storage.delivery_plan_service import DeliveryPlanService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed_meeting(tmp_path: Path, **overrides) -> MeetingMinutes:
    """Create and persist a completed MeetingMinutes in the workspace."""
    from studio.storage.workspace import StudioWorkspace

    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    defaults = {
        "id": "meet_001",
        "requirement_id": "req_001",
        "title": "Kickoff Meeting",
        "status": "completed",
        "decisions": ["Use React"],
        "consensus_points": ["Scope agreed"],
    }
    defaults.update(overrides)
    meeting = MeetingMinutes(**defaults)
    ws.meetings.save(meeting)
    return meeting


def _create_session(
    tmp_path: Path,
    project_id: str = "proj_001",
    agent: str = "dev",
) -> ProjectAgentSession:
    """Create and persist a ProjectAgentSession in the workspace."""
    from studio.storage.workspace import StudioWorkspace

    ws = StudioWorkspace(tmp_path)
    session = ProjectAgentSession(
        project_id=project_id,
        requirement_id="req_001",
        agent=agent,
        session_id="sess_abc",
    )
    ws.sessions.save(session)
    return session


def _planner_output(
    *,
    tasks: list[dict] | None = None,
    gate_items: list[dict] | None = None,
) -> dict:
    """Build a planner_output dict with the given tasks and optional gate items."""
    output: dict = {}
    output["tasks"] = tasks if tasks is not None else [
        {
            "title": "Design system architecture",
            "description": "Create architecture docs",
            "owner_agent": "design",
            "depends_on": [],
            "acceptance_criteria": ["Docs reviewed"],
        },
        {
            "title": "Implement backend",
            "description": "Build the API",
            "owner_agent": "dev",
            "depends_on": ["Design system architecture"],
            "acceptance_criteria": ["All tests pass"],
        },
    ]
    if gate_items is not None:
        output["decision_gate"] = {"items": gate_items}
    return output


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def svc(tmp_path: Path) -> DeliveryPlanService:
    return DeliveryPlanService(tmp_path)


# ===========================================================================
# _has_cycle
# ===========================================================================


class TestHasCycle:
    @staticmethod
    def test_no_cycle(svc: DeliveryPlanService) -> None:
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": [],
        }
        assert svc._has_cycle(graph) is False

    @staticmethod
    def test_simple_two_node_cycle(svc: DeliveryPlanService) -> None:
        graph = {
            "a": ["b"],
            "b": ["a"],
        }
        assert svc._has_cycle(graph) is True

    @staticmethod
    def test_self_dependency(svc: DeliveryPlanService) -> None:
        graph = {
            "a": ["a"],
        }
        assert svc._has_cycle(graph) is True

    @staticmethod
    def test_three_node_cycle(svc: DeliveryPlanService) -> None:
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": ["a"],
        }
        assert svc._has_cycle(graph) is True

    @staticmethod
    def test_empty_graph(svc: DeliveryPlanService) -> None:
        assert svc._has_cycle({}) is False

    @staticmethod
    def test_disconnected_with_one_cycle(svc: DeliveryPlanService) -> None:
        graph = {
            "a": ["b"],
            "b": ["a"],
            "c": [],
            "d": ["e"],
            "e": [],
        }
        assert svc._has_cycle(graph) is True


# ===========================================================================
# generate_plan
# ===========================================================================


class TestGeneratePlan:
    @staticmethod
    def test_creates_plan_tasks_and_gate(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Which framework?",
                "context": "Need to decide",
                "options": ["React", "Vue"],
            },
        ]
        result = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )

        plan = result["plan"]
        assert plan.meeting_id == "meet_001"
        assert plan.requirement_id == "req_001"
        assert plan.project_id == "proj_001"
        assert plan.status == "awaiting_user_decision"
        assert len(result["tasks"]) == 2

        # First task has no deps -> ready
        assert result["tasks"][0].status == "ready"
        # Second task depends on first -> blocked
        assert result["tasks"][1].status == "blocked"
        assert len(result["tasks"][1].depends_on_task_ids) == 1

        gate = result["decision_gate"]
        assert gate is not None
        assert gate.status == "open"
        assert len(gate.items) == 1

    @staticmethod
    def test_creates_active_plan_when_no_gate(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        result = svc.generate_plan(
            "meet_001",
            _planner_output(),  # no gate_items
            "proj_001",
        )

        assert result["plan"].status == "active"
        assert result["decision_gate"] is None

    @staticmethod
    def test_rejects_unknown_owner_agent(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        bad_output = _planner_output(tasks=[
            {
                "title": "Do stuff",
                "description": "Things",
                "owner_agent": "unknown_agent",
                "depends_on": [],
            },
        ])
        with pytest.raises(ValueError, match="unknown owner_agent"):
            svc.generate_plan("meet_001", bad_output, "proj_001")

    @staticmethod
    def test_rejects_cyclic_dependencies(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        cyclic_output = _planner_output(tasks=[
            {
                "title": "Task A",
                "description": "A",
                "owner_agent": "dev",
                "depends_on": ["Task B"],
            },
            {
                "title": "Task B",
                "description": "B",
                "owner_agent": "dev",
                "depends_on": ["Task A"],
            },
        ])
        with pytest.raises(ValueError, match="cycle"):
            svc.generate_plan("meet_001", cyclic_output, "proj_001")

    @staticmethod
    def test_rejects_incomplete_meeting(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path, status="draft")
        with pytest.raises(ValueError, match="not completed"):
            svc.generate_plan("meet_001", _planner_output(), "proj_001")

    @staticmethod
    def test_returns_existing_plan(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        first = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        second = svc.generate_plan("meet_001", _planner_output(), "proj_001")

        assert second["plan"].id == first["plan"].id
        assert len(second["tasks"]) == len(first["tasks"])

    @staticmethod
    def test_rejects_unknown_depends_on_reference(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        bad_output = _planner_output(tasks=[
            {
                "title": "Task A",
                "description": "A",
                "owner_agent": "dev",
                "depends_on": ["Nonexistent Task"],
            },
        ])
        with pytest.raises(ValueError, match="unknown task"):
            svc.generate_plan("meet_001", bad_output, "proj_001")


# ===========================================================================
# resolve_gate
# ===========================================================================


class TestResolveGate:
    @staticmethod
    def test_activates_plan(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Which framework?",
                "context": "Need to decide",
                "options": ["React", "Vue"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id

        result = svc.resolve_gate(gate_id, {"q1": "React"})

        assert result["gate"].status == "resolved"
        assert result["gate"].resolution_version == 1
        assert result["gate"].items[0].resolution == "React"
        assert result["plan"].status == "active"
        assert result["plan"].decision_resolution_version == 1

    @staticmethod
    def test_rejects_partial_resolution(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Framework?",
                "context": "Need to choose a framework",
                "options": ["React", "Vue"],
            },
            {
                "id": "q2",
                "question": "Language?",
                "context": "Need to choose a language",
                "options": ["TypeScript", "JavaScript"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id

        with pytest.raises(ValueError, match="no resolution"):
            svc.resolve_gate(gate_id, {"q1": "React"})  # missing q2

    @staticmethod
    def test_rejects_invalid_option(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Framework?",
                "context": "Need to choose",
                "options": ["React", "Vue"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id

        with pytest.raises(ValueError, match="not a valid option"):
            svc.resolve_gate(gate_id, {"q1": "Svelte"})

    @staticmethod
    def test_rejects_already_resolved_gate(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Framework?",
                "context": "Need to choose",
                "options": ["React", "Vue"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id
        svc.resolve_gate(gate_id, {"q1": "React"})

        with pytest.raises(ValueError, match="not open"):
            svc.resolve_gate(gate_id, {"q1": "Vue"})


# ===========================================================================
# start_task
# ===========================================================================


class TestStartTask:
    @staticmethod
    def test_succeeds_with_session(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")

        # The first task (design) has no deps, plan is active (no gate)
        design_task = gen["tasks"][0]
        _create_session(tmp_path, project_id="proj_001", agent="design")

        updated = svc.start_task(design_task.id, "sess_run_001")
        assert updated.status == "in_progress"

    @staticmethod
    def test_fails_when_gate_open(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Which framework?",
                "context": "Need to decide",
                "options": ["React", "Vue"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        design_task = gen["tasks"][0]
        _create_session(tmp_path, project_id="proj_001", agent="design")

        with pytest.raises(ValueError, match="unresolved decision gate"):
            svc.start_task(design_task.id, "sess_run_001")

    @staticmethod
    def test_fails_when_session_missing(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]
        # No session created

        with pytest.raises(ValueError, match="no session found"):
            svc.start_task(design_task.id, "sess_run_001")

    @staticmethod
    def test_fails_when_task_not_ready(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        # Second task has deps, so status is "blocked"
        blocked_task = gen["tasks"][1]

        with pytest.raises(ValueError, match="not ready"):
            svc.start_task(blocked_task.id, "sess_run_001")

    @staticmethod
    def test_fails_when_dependency_not_done(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]
        dev_task = gen["tasks"][1]

        # Create sessions for both agents
        _create_session(tmp_path, project_id="proj_001", agent="design")
        _create_session(tmp_path, project_id="proj_001", agent="dev")

        # Start the design task first so it's in_progress
        svc.start_task(design_task.id, "sess_run_001")

        # Manually mark dev task as "ready" (simulating dep resolution)
        # but leave design as "in_progress" so the dependency check fails
        from studio.storage.workspace import StudioWorkspace

        ws = StudioWorkspace(tmp_path)
        dev = ws.delivery_tasks.get(dev_task.id)
        dev = dev.model_copy(update={"status": "ready"})
        ws.delivery_tasks.save(dev)

        with pytest.raises(ValueError, match="not done"):
            svc.start_task(dev_task.id, "sess_run_002")

    @staticmethod
    def test_starts_after_gate_resolved(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gate_items = [
            {
                "id": "q1",
                "question": "Framework?",
                "context": "Need to decide",
                "options": ["React", "Vue"],
            },
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        design_task = gen["tasks"][0]
        gate_id = gen["decision_gate"].id

        # Resolve the gate first
        svc.resolve_gate(gate_id, {"q1": "React"})

        # Now create the session and start the task
        _create_session(tmp_path, project_id="proj_001", agent="design")
        updated = svc.start_task(design_task.id, "sess_run_001")
        assert updated.status == "in_progress"


# ===========================================================================
# list_board
# ===========================================================================


class TestListBoard:
    @staticmethod
    def test_returns_all_items(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        svc.generate_plan("meet_001", _planner_output(), "proj_001")

        board = svc.list_board()
        assert len(board["plans"]) == 1
        assert len(board["tasks"]) == 2
        assert len(board["decision_gates"]) == 0  # no gate

    @staticmethod
    def test_filters_by_requirement_id(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, id="meet_001", requirement_id="req_001")
        _completed_meeting(tmp_path, id="meet_002", requirement_id="req_002")
        svc.generate_plan("meet_001", _planner_output(), "proj_001")
        svc.generate_plan("meet_002", _planner_output(), "proj_001")

        board = svc.list_board(requirement_id="req_001")
        assert len(board["plans"]) == 1
        assert board["plans"][0].requirement_id == "req_001"
        assert len(board["tasks"]) == 2
        assert all(t.requirement_id == "req_001" for t in board["tasks"])

    @staticmethod
    def test_empty_board(svc: DeliveryPlanService) -> None:
        board = svc.list_board()
        assert board["plans"] == []
        assert board["tasks"] == []
        assert board["decision_gates"] == []


# ===========================================================================
# resolve_gate — preview task promotion
# ===========================================================================


class TestResolveGatePreviewPromotion:
    @staticmethod
    def test_preview_tasks_promoted_to_ready(svc: DeliveryPlanService, tmp_path: Path) -> None:
        """Preview tasks should be promoted to ready after gate resolution."""
        _completed_meeting(tmp_path)
        gate_items = [
            {"id": "q1", "question": "Framework?", "context": "c", "options": ["React", "Vue"]},
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id
        task_ids = [t.id for t in gen["tasks"]]

        # Manually set tasks to preview status
        from studio.storage.workspace import StudioWorkspace
        ws = StudioWorkspace(tmp_path)
        for tid in task_ids:
            t = ws.delivery_tasks.get(tid)
            ws.delivery_tasks.save(t.model_copy(update={"status": "preview"}))

        svc.resolve_gate(gate_id, {"q1": "React"})

        # Verify tasks are now ready with the correct version stamp
        for tid in task_ids:
            t = ws.delivery_tasks.get(tid)
            assert t.status == "ready", f"task {tid} should be ready, got {t.status}"
            assert t.decision_resolution_version == 1


# ===========================================================================
# start_task — decision_resolution_version check
# ===========================================================================


class TestStartTaskVersionCheck:
    @staticmethod
    def test_rejects_stale_resolution_version(svc: DeliveryPlanService, tmp_path: Path) -> None:
        """Tasks with stale decision_resolution_version should not start."""
        _completed_meeting(tmp_path)
        gate_items = [
            {"id": "q1", "question": "Framework?", "context": "c", "options": ["React", "Vue"]},
        ]
        gen = svc.generate_plan(
            "meet_001",
            _planner_output(gate_items=gate_items),
            "proj_001",
        )
        gate_id = gen["decision_gate"].id
        task = gen["tasks"][0]

        # Resolve gate (stamps version=1 on plan)
        svc.resolve_gate(gate_id, {"q1": "React"})

        # Manually set task to version=0 (stale)
        from studio.storage.workspace import StudioWorkspace
        ws = StudioWorkspace(tmp_path)
        t = ws.delivery_tasks.get(task.id)
        ws.delivery_tasks.save(t.model_copy(update={"decision_resolution_version": 0}))

        _create_session(tmp_path, project_id="proj_001", agent="design")
        with pytest.raises(ValueError, match="decision_resolution_version"):
            svc.start_task(task.id, "sess_run_001")


# ===========================================================================
# complete_task
# ===========================================================================


class TestCompleteTask:
    @staticmethod
    def test_completes_task_and_persists_result(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]
        _create_session(tmp_path, project_id="proj_001", agent="design")
        svc.start_task(design_task.id, "sess_run_001")

        result = svc.complete_task(
            design_task.id,
            summary="Architecture designed",
            changed_files=["docs/arch.md"],
            tests_or_checks=["lint docs/"],
        )
        assert result["task"].status == "done"
        assert result["task"].execution_result_id is not None
        assert result["execution_result"].summary == "Architecture designed"
        assert result["execution_result"].changed_files == ["docs/arch.md"]

    @staticmethod
    def test_releases_lease_on_complete(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]
        _create_session(tmp_path, project_id="proj_001", agent="design")
        svc.start_task(design_task.id, "sess_run_001")

        svc.complete_task(design_task.id, summary="Done")

        # Lease should be released, so another task can start
        from studio.storage.session_lease import SessionLeaseManager
        lease_mgr = SessionLeaseManager(tmp_path)
        assert lease_mgr.is_available("proj_001", "design") is True

    @staticmethod
    def test_marks_plan_completed_when_all_done(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(tasks=[
            {"title": "Task A", "description": "a", "owner_agent": "dev", "depends_on": [], "acceptance_criteria": []},
        ]), "proj_001")
        task = gen["tasks"][0]
        _create_session(tmp_path, project_id="proj_001", agent="dev")
        svc.start_task(task.id, "sess_run_001")

        result = svc.complete_task(task.id, summary="Done")
        assert result["task"].status == "done"

        from studio.storage.workspace import StudioWorkspace
        ws = StudioWorkspace(tmp_path)
        plan = ws.delivery_plans.get(gen["plan"].id)
        assert plan.status == "completed"

    @staticmethod
    def test_rejects_not_in_progress(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        task = gen["tasks"][0]
        with pytest.raises(ValueError, match="not in_progress"):
            svc.complete_task(task.id, summary="Nope")


# ===========================================================================
# get_dependency_outputs
# ===========================================================================


class TestGetDependencyOutputs:
    @staticmethod
    def test_returns_upstream_execution_results(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]
        dev_task = gen["tasks"][1]

        # Start and complete the design task
        _create_session(tmp_path, project_id="proj_001", agent="design")
        svc.start_task(design_task.id, "sess_run_001")
        svc.complete_task(
            design_task.id,
            summary="Architecture done",
            output_artifact_ids=["artifact_arch"],
            changed_files=["docs/arch.md"],
        )

        # Get dependency outputs for the dev task
        outputs = svc.get_dependency_outputs(dev_task.id)
        assert len(outputs) == 1
        assert outputs[0]["task_id"] == design_task.id
        assert outputs[0]["summary"] == "Architecture done"
        assert outputs[0]["output_artifact_ids"] == ["artifact_arch"]

    @staticmethod
    def test_returns_empty_for_no_deps(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        gen = svc.generate_plan("meet_001", _planner_output(), "proj_001")
        design_task = gen["tasks"][0]  # no deps
        outputs = svc.get_dependency_outputs(design_task.id)
        assert outputs == []
