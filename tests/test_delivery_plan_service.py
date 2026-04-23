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
