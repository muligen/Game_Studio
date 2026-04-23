"""Tests for delivery API routes (generate plan, board listing, resolve gate, start task)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.api.main import create_app
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.session import ProjectAgentSession
from studio.storage.workspace import StudioWorkspace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_meeting(workspace: Path, meeting_id: str, **overrides) -> MeetingMinutes:
    """Create and persist a completed MeetingMinutes in the workspace."""
    ws = StudioWorkspace(workspace / ".studio-data")
    ws.ensure_layout()
    defaults = {
        "id": meeting_id,
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


def _seed_session(
    workspace: Path,
    project_id: str = "proj_001",
    agent: str = "dev",
) -> ProjectAgentSession:
    """Create and persist a ProjectAgentSession in the workspace."""
    ws = StudioWorkspace(workspace / ".studio-data")
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
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    return TestClient(create_app())


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create and return a workspace directory (tmp_path / 'ws')."""
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


# ===========================================================================
# Tests
# ===========================================================================


class TestGenerateDeliveryPlan:
    """POST /api/meetings/{meeting_id}/delivery-plan"""

    @staticmethod
    def test_200_generates_plan_with_tasks(
        client: TestClient, workspace: Path,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(),
        }
        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["meeting_id"] == "meet_001"
        assert data["plan"]["status"] == "active"
        assert len(data["tasks"]) == 2
        assert data["decision_gate"] is None

    @staticmethod
    def test_404_missing_meeting(client: TestClient, workspace: Path) -> None:
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(),
        }
        resp = client.post(
            "/api/meetings/nonexistent/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @staticmethod
    def test_400_incomplete_meeting(client: TestClient, workspace: Path) -> None:
        _seed_meeting(workspace, "meet_001", status="draft")
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(),
        }
        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )
        assert resp.status_code == 400


class TestListDeliveryBoard:
    """GET /api/delivery-board"""

    @staticmethod
    def test_200_returns_board(client: TestClient, workspace: Path) -> None:
        _seed_meeting(workspace, "meet_001")
        # Generate a plan so there is data on the board
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(),
        }
        client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )

        resp = client.get(
            "/api/delivery-board",
            params={"workspace": str(workspace)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["plans"]) == 1
        assert len(data["tasks"]) == 2
        assert data["decision_gates"] == []

    @staticmethod
    def test_200_empty_board(client: TestClient, workspace: Path) -> None:
        resp = client.get(
            "/api/delivery-board",
            params={"workspace": str(workspace)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plans"] == []
        assert data["tasks"] == []
        assert data["decision_gates"] == []


class TestResolveGate:
    """POST /api/kickoff-decision-gates/{gate_id}/resolve"""

    @staticmethod
    def test_200_resolves_gate_and_activates_plan(
        client: TestClient, workspace: Path,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        gate_items = [
            {
                "id": "q1",
                "question": "Which framework?",
                "context": "Need to decide",
                "options": ["React", "Vue"],
            },
        ]
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(gate_items=gate_items),
        }
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )
        gate_id = gen_resp.json()["decision_gate"]["id"]

        resolve_resp = client.post(
            f"/api/kickoff-decision-gates/{gate_id}/resolve",
            params={"workspace": str(workspace)},
            json={"resolutions": {"q1": "React"}},
        )
        assert resolve_resp.status_code == 200
        data = resolve_resp.json()
        assert data["gate"]["status"] == "resolved"
        assert data["gate"]["items"][0]["resolution"] == "React"
        assert data["plan"]["status"] == "active"


class TestStartTask:
    """POST /api/delivery-tasks/{task_id}/start"""

    @staticmethod
    def test_200_starts_task(client: TestClient, workspace: Path) -> None:
        _seed_meeting(workspace, "meet_001")
        body = {
            "project_id": "proj_001",
            "planner_output": _planner_output(),
        }
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json=body,
        )
        # First task has no deps and plan is active (no gate)
        task_id = gen_resp.json()["tasks"][0]["id"]

        # Set up the project session so start_task succeeds
        _seed_session(workspace, project_id="proj_001", agent="design")

        start_resp = client.post(
            f"/api/delivery-tasks/{task_id}/start",
            params={"workspace": str(workspace)},
            json={"session_id": "sess_run_001"},
        )
        assert start_resp.status_code == 200
        task = start_resp.json()
        assert task["status"] == "in_progress"
        assert task["id"] == task_id
