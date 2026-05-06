from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.api.main import create_app
from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.schemas.session import ProjectAgentSession
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.workspace import StudioWorkspace


def _seed_meeting(workspace: Path, meeting_id: str, **overrides: object) -> MeetingMinutes:
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
    ws.requirements.save(RequirementCard(id="req_001", title="Turn-based battle MVP", status="approved"))
    return meeting


def _seed_session(
    workspace: Path,
    *,
    project_id: str = "proj_001",
    agent: str = "design",
) -> ProjectAgentSession:
    ws = StudioWorkspace(workspace / ".studio-data")
    session = ProjectAgentSession(
        project_id=project_id,
        requirement_id="req_001",
        agent=agent,
        session_id=f"sess_{agent}_001",
    )
    ws.sessions.save(session)
    return session


def _planner_payload(
    *,
    gate_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "tasks": [
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
        ],
        "decision_gate": {"items": gate_items or []},
    }


class FakePlanner:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or _planner_payload()

    def generate(self, context: dict[str, object]) -> dict[str, object]:
        return self.payload


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture()
def planner(monkeypatch: pytest.MonkeyPatch) -> FakePlanner:
    planner = FakePlanner()

    def _get_service(workspace: str) -> DeliveryPlanService:
        return DeliveryPlanService(
            resolve_workspace_root(workspace),
            planner=planner,
            project_root=resolve_project_root(workspace),
        )

    monkeypatch.setattr("studio.api.routes.delivery._get_service", _get_service)
    return planner


class TestGenerateDeliveryPlan:
    @staticmethod
    def test_200_generates_plan_from_backend_planner(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")

        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["meeting_id"] == "meet_001"
        assert data["plan"]["status"] == "active"
        assert len(data["tasks"]) == 2
        assert data["decision_gate"] is None

    @staticmethod
    def test_active_plan_generation_starts_delivery_runner(
        client: TestClient, workspace: Path, planner: FakePlanner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        calls: list[tuple[Path, Path, str]] = []

        def _fake_run_delivery_plan(workspace_root: Path, project_root: Path, plan_id: str) -> None:
            calls.append((workspace_root, project_root, plan_id))

        monkeypatch.setattr("studio.api.routes.delivery.run_delivery_plan", _fake_run_delivery_plan)

        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )

        assert resp.status_code == 200
        assert calls == [
            (
                resolve_workspace_root(str(workspace)),
                resolve_project_root(str(workspace)),
                resp.json()["plan"]["id"],
            )
        ]

    @staticmethod
    def test_active_plan_generation_returns_before_delivery_runner_finishes(
        client: TestClient, workspace: Path, planner: FakePlanner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        started = threading.Event()
        release = threading.Event()

        def _fake_run_delivery_plan(workspace_root: Path, project_root: Path, plan_id: str) -> None:
            _ = workspace_root, project_root, plan_id
            started.set()
            release.wait(timeout=2)

        monkeypatch.setattr("studio.api.routes.delivery.run_delivery_plan", _fake_run_delivery_plan)

        before = time.monotonic()
        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        elapsed = time.monotonic() - before
        release.set()

        assert resp.status_code == 200
        assert elapsed < 0.5
        assert started.wait(timeout=1)

    @staticmethod
    def test_404_missing_meeting(client: TestClient, workspace: Path, planner: FakePlanner) -> None:
        resp = client.post(
            "/api/meetings/nonexistent/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @staticmethod
    def test_422_rejects_old_planner_output_shape(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")

        resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001", "planner_output": _planner_payload()},
        )

        assert resp.status_code == 422

    @staticmethod
    def test_200_generates_plan_when_workspace_is_studio_data_dir(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_002")

        resp = client.post(
            "/api/meetings/meet_002/delivery-plan",
            params={"workspace": str(workspace / ".studio-data")},
            json={"project_id": "proj_001"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["meeting_id"] == "meet_002"
        assert len(data["tasks"]) == 2


class TestListDeliveryBoard:
    @staticmethod
    def test_200_returns_board(client: TestClient, workspace: Path, planner: FakePlanner) -> None:
        _seed_meeting(workspace, "meet_001")
        client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )

        resp = client.get("/api/delivery-board", params={"workspace": str(workspace)})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["plans"]) == 1
        assert len(data["tasks"]) == 2
        assert data["decision_gates"] == []


class TestResolveGate:
    @staticmethod
    def test_200_resolves_gate_and_activates_plan(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "q1",
                    "question": "Which framework?",
                    "context": "Need to decide",
                    "options": ["React", "Vue"],
                },
            ],
        )
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
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
        assert data["plan"]["status"] == "active"

    @staticmethod
    def test_resolving_gate_starts_delivery_runner(
        client: TestClient, workspace: Path, planner: FakePlanner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "q1",
                    "question": "Which framework?",
                    "context": "Need to decide",
                    "options": ["React", "Vue"],
                },
            ],
        )
        calls: list[str] = []

        def _fake_run_delivery_plan(workspace_root: Path, project_root: Path, plan_id: str) -> None:
            calls.append(plan_id)

        monkeypatch.setattr("studio.api.routes.delivery.run_delivery_plan", _fake_run_delivery_plan)
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        gate_id = gen_resp.json()["decision_gate"]["id"]

        resolve_resp = client.post(
            f"/api/kickoff-decision-gates/{gate_id}/resolve",
            params={"workspace": str(workspace)},
            json={"resolutions": {"q1": "React"}},
        )

        assert resolve_resp.status_code == 200
        assert calls == [resolve_resp.json()["plan"]["id"]]


class TestStartTask:
    @staticmethod
    def test_200_starts_task_without_frontend_session_id(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        task_id = gen_resp.json()["tasks"][0]["id"]
        _seed_session(workspace, project_id="proj_001", agent="design")

        start_resp = client.post(
            f"/api/delivery-tasks/{task_id}/start",
            params={"workspace": str(workspace)},
            json={},
        )

        assert start_resp.status_code == 200
        task = start_resp.json()
        assert task["status"] == "in_progress"

    @staticmethod
    def test_400_fails_when_project_session_missing(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        task_id = gen_resp.json()["tasks"][0]["id"]

        start_resp = client.post(
            f"/api/delivery-tasks/{task_id}/start",
            params={"workspace": str(workspace)},
            json={},
        )

        assert start_resp.status_code == 400
        assert "no session found" in start_resp.json()["detail"]


class TestRetryTask:
    @staticmethod
    def test_200_retries_failed_task(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        task_id = gen_resp.json()["tasks"][0]["id"]
        ws = StudioWorkspace(workspace / ".studio-data")
        task = ws.delivery_tasks.get(task_id)
        ws.delivery_tasks.save(
            task.model_copy(
                update={
                    "status": "failed",
                    "last_error": "claude crashed",
                    "attempt_count": 1,
                    "execution_result_id": f"result_{task_id}_attempt_1",
                }
            )
        )

        retry_resp = client.post(
            f"/api/delivery-tasks/{task_id}/retry",
            params={"workspace": str(workspace)},
            json={},
        )

        assert retry_resp.status_code == 200
        retried = retry_resp.json()
        assert retried["status"] == "ready"
        assert retried["last_error"] is None
        assert retried["attempt_count"] == 1
        assert retried["execution_result_id"] is None

    @staticmethod
    def test_400_rejects_retry_for_non_failed_task(
        client: TestClient, workspace: Path, planner: FakePlanner,
    ) -> None:
        _seed_meeting(workspace, "meet_001")
        gen_resp = client.post(
            "/api/meetings/meet_001/delivery-plan",
            params={"workspace": str(workspace)},
            json={"project_id": "proj_001"},
        )
        task_id = gen_resp.json()["tasks"][0]["id"]

        retry_resp = client.post(
            f"/api/delivery-tasks/{task_id}/retry",
            params={"workspace": str(workspace)},
            json={},
        )

        assert retry_resp.status_code == 400
        assert "not failed" in retry_resp.json()["detail"]
