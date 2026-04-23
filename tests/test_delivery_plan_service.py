from __future__ import annotations

from pathlib import Path

import pytest

from studio.llm import ClaudeRoleError
from studio.schemas.design_doc import DesignDoc
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.schemas.session import ProjectAgentSession
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.workspace import StudioWorkspace


def _completed_meeting(tmp_path: Path, **overrides: object) -> MeetingMinutes:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    defaults = {
        "id": "meet_001",
        "requirement_id": "req_001",
        "title": "Kickoff Meeting",
        "status": "completed",
        "decisions": ["Use turn-based combat"],
        "consensus_points": ["Scope agreed"],
        "pending_user_decisions": [],
    }
    defaults.update(overrides)
    meeting = MeetingMinutes(**defaults)
    ws.meetings.save(meeting)
    return meeting


def _requirement(tmp_path: Path) -> RequirementCard:
    ws = StudioWorkspace(tmp_path)
    req = RequirementCard(id="req_001", title="Turn-based battle MVP", status="approved")
    ws.requirements.save(req)
    return req


def _design_doc(tmp_path: Path) -> DesignDoc:
    ws = StudioWorkspace(tmp_path)
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Battle Loop Design",
        summary="Summarizes the intended turn loop.",
        core_rules=["Units act by speed order"],
        acceptance_criteria=["One full battle can finish"],
        open_questions=[],
        status="approved",
    )
    ws.design_docs.save(doc)
    return doc


def _create_session(
    tmp_path: Path,
    *,
    project_id: str = "proj_001",
    agent: str = "design",
    session_id: str = "sess_design_001",
) -> ProjectAgentSession:
    ws = StudioWorkspace(tmp_path)
    session = ProjectAgentSession(
        project_id=project_id,
        requirement_id="req_001",
        agent=agent,
        session_id=session_id,
    )
    ws.sessions.save(session)
    return session


def _planner_payload(
    *,
    tasks: list[dict[str, object]] | None = None,
    gate_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "tasks": tasks
        if tasks is not None
        else [
            {
                "title": "Design battle flow",
                "description": "Write the flow spec",
                "owner_agent": "design",
                "depends_on": [],
                "acceptance_criteria": ["Spec reviewed"],
            },
            {
                "title": "Implement battle flow",
                "description": "Build the core loop",
                "owner_agent": "dev",
                "depends_on": ["Design battle flow"],
                "acceptance_criteria": ["Tests pass"],
            },
        ],
        "decision_gate": {"items": gate_items or []},
    }


class FakePlanner:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or _planner_payload()
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate(self, context: dict[str, object]) -> dict[str, object]:
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture()
def planner() -> FakePlanner:
    return FakePlanner()


@pytest.fixture()
def svc(tmp_path: Path, planner: FakePlanner) -> DeliveryPlanService:
    return DeliveryPlanService(tmp_path, planner=planner)


class TestGeneratePlan:
    @staticmethod
    def test_invokes_planner_with_workspace_context(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Pick elemental scope"])
        _requirement(tmp_path)
        _design_doc(tmp_path)
        _create_session(tmp_path, project_id="proj_001", agent="design")

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "active"
        assert len(result["tasks"]) == 2
        assert planner.calls, "planner should have been invoked"
        context = planner.calls[0]
        assert context["meeting"]["id"] == "meet_001"
        assert context["requirement"]["id"] == "req_001"
        assert context["design_docs"][0]["id"] == "design_001"
        assert context["project_sessions"][0]["agent"] == "design"

    @staticmethod
    def test_rejects_incomplete_meeting(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path, status="draft")
        _requirement(tmp_path)

        with pytest.raises(ValueError, match="not completed"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_rejects_unknown_owner_agent(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            tasks=[
                {
                    "title": "Do stuff",
                    "description": "Things",
                    "owner_agent": "unknown_agent",
                    "depends_on": [],
                    "acceptance_criteria": [],
                },
            ],
        )

        with pytest.raises(ValueError, match="unknown owner_agent"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_rejects_cyclic_dependencies(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            tasks=[
                {
                    "title": "Task A",
                    "description": "A",
                    "owner_agent": "dev",
                    "depends_on": ["Task B"],
                    "acceptance_criteria": [],
                },
                {
                    "title": "Task B",
                    "description": "B",
                    "owner_agent": "dev",
                    "depends_on": ["Task A"],
                    "acceptance_criteria": [],
                },
            ],
        )

        with pytest.raises(ValueError, match="cycle"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_surfaces_planner_errors_without_fallback(tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        svc = DeliveryPlanService(tmp_path, planner=FakePlanner(error=ClaudeRoleError("claude_disabled")))

        with pytest.raises(ClaudeRoleError, match="claude_disabled"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_creates_preview_tasks_when_gate_exists(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Choose status effect scope"])
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "awaiting_user_decision"
        assert result["decision_gate"] is not None
        assert [task.status for task in result["tasks"]] == ["preview", "preview"]

    @staticmethod
    def test_returns_existing_plan_without_reinvoking_planner(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)

        first = svc.generate_plan("meet_001", "proj_001")
        second = svc.generate_plan("meet_001", "proj_001")

        assert second["plan"].id == first["plan"].id
        assert len(planner.calls) == 1


class TestResolveGate:
    @staticmethod
    def test_promotes_preview_tasks_and_stamps_versions(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")

        result = svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})

        assert result["gate"].status == "resolved"
        assert result["gate"].resolution_version == 1
        assert result["plan"].status == "active"
        assert result["plan"].decision_resolution_version == 1

        ws = StudioWorkspace(tmp_path)
        tasks = [ws.delivery_tasks.get(task.id) for task in generated["tasks"]]
        assert tasks[0].status == "ready"
        assert tasks[0].decision_resolution_version == 1
        assert tasks[1].status == "blocked"
        assert tasks[1].decision_resolution_version == 1


class TestStartTask:
    @staticmethod
    def test_rejects_preview_task_before_gate_resolution(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")

        with pytest.raises(ValueError, match="not ready"):
            svc.start_task(generated["tasks"][0].id)

    @staticmethod
    def test_uses_server_side_project_session_lookup(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        generated = svc.generate_plan("meet_001", "proj_001")
        _create_session(tmp_path, project_id="proj_001", agent="design", session_id="sess_design_123")

        task = svc.start_task(generated["tasks"][0].id)

        assert task.status == "in_progress"
        lease = StudioWorkspace(tmp_path).session_leases.get("proj_001_design")
        assert lease.session_id == "sess_design_123"

    @staticmethod
    def test_rejects_missing_project_session(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        generated = svc.generate_plan("meet_001", "proj_001")

        with pytest.raises(ValueError, match="no session found"):
            svc.start_task(generated["tasks"][0].id)

    @staticmethod
    def test_rejects_missing_task_decision_version_after_gate_resolution(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")
        svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})
        _create_session(tmp_path, project_id="proj_001", agent="design")

        ws = StudioWorkspace(tmp_path)
        task = ws.delivery_tasks.get(generated["tasks"][0].id)
        ws.delivery_tasks.save(task.model_copy(update={"decision_resolution_version": None}))

        with pytest.raises(ValueError, match="decision_resolution_version"):
            svc.start_task(task.id)

    @staticmethod
    def test_rejects_stale_task_decision_version(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")
        svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})
        _create_session(tmp_path, project_id="proj_001", agent="design")

        ws = StudioWorkspace(tmp_path)
        task = ws.delivery_tasks.get(generated["tasks"][0].id)
        ws.delivery_tasks.save(task.model_copy(update={"decision_resolution_version": 0}))

        with pytest.raises(ValueError, match="decision_resolution_version"):
            svc.start_task(task.id)
