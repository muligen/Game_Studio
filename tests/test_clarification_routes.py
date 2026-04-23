from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def client():
    from studio.api.main import create_app
    return TestClient(create_app())


@pytest.fixture
def workspace(tmp_path: Path) -> str:
    ws = tmp_path / ".studio-data"
    workspace = StudioWorkspace(ws)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat system"))
    return str(tmp_path)


def test_start_creates_session(client, workspace):
    response = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["requirement_id"] == "req_001"
    assert data["session"]["status"] == "collecting"


def test_start_returns_existing_session(client, workspace):
    r1 = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    r2 = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    assert r1.json()["session"]["id"] == r2.json()["session"]["id"]


def test_start_fails_for_missing_requirement(client, workspace):
    response = client.post(f"/api/clarifications/requirements/req_999/session?workspace={workspace}")
    assert response.status_code == 404


def test_send_message_appends_to_session(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    with patch("studio.api.routes.clarifications.ClaudeRoleAdapter") as MockAdapter:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = type("Payload", (), {
            "reply": "Should combat be real-time or turn-based?",
            "meeting_context": {
                "summary": "Combat system",
                "goals": [],
                "constraints": [],
                "open_questions": ["Real-time or turn-based?"],
                "acceptance_criteria": [],
                "risks": [],
                "references": [],
                "validated_attendees": ["design", "dev"],
            },
            "readiness": {"ready": False, "missing_fields": ["acceptance_criteria"], "notes": []},
        })()
        MockAdapter.return_value = mock_instance

        response = client.post(
            f"/api/clarifications/requirements/req_001/messages?workspace={workspace}",
            json={"message": "I want a combat system.", "session_id": session_id},
        )

    assert MockAdapter.call_args.kwargs["timeout_seconds"] == 45
    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"] == "Should combat be real-time or turn-based?"
    session = data["session"]
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_send_message_rejects_empty_message(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    response = client.post(
        f"/api/clarifications/requirements/req_001/messages?workspace={workspace}",
        json={"message": "", "session_id": session_id},
    )
    assert response.status_code == 422


def test_send_message_persists_user_message_when_agent_fails(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    with patch("studio.api.routes.clarifications.ClaudeRoleAdapter") as MockAdapter:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = RuntimeError("agent timed out")
        MockAdapter.return_value = mock_instance

        response = client.post(
            f"/api/clarifications/requirements/req_001/messages?workspace={workspace}",
            json={"message": "I want a combat system.", "session_id": session_id},
        )

    assert response.status_code == 502
    store = StudioWorkspace(Path(workspace) / ".studio-data")
    session = store.clarifications.get(session_id)
    assert session.status == "failed"
    assert len(session.messages) == 1
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "I want a combat system."


def test_kickoff_rejects_unready_session(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    response = client.post(
        f"/api/clarifications/requirements/req_001/kickoff?workspace={workspace}",
        json={"session_id": session_id},
    )
    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


def test_kickoff_creates_project_and_runs_meeting(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    # Manually set session to ready
    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    session = ws.clarifications.get(session_id)
    from studio.schemas.clarification import MeetingContextDraft, ReadinessCheck
    session = session.model_copy(update={
        "meeting_context": MeetingContextDraft(
            summary="Combat system",
            goals=["Define MVP combat loop"],
            acceptance_criteria=["3v3 battle completes"],
            risks=["Scope growth"],
            validated_attendees=["design", "dev"],
        ),
        "readiness": ReadinessCheck(ready=True, missing_fields=[]),
        "status": "ready",
    })
    ws.clarifications.save(session)

    with patch("studio.api.routes.clarifications.SessionRegistry") as MockRegistry, \
         patch("studio.api.routes.clarifications.build_meeting_graph") as MockGraph:
        mock_reg = MagicMock()
        mock_reg.create_all.return_value = []
        MockRegistry.return_value = mock_reg

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "moderator_minutes",
            "minutes": {"id": "meeting_001", "requirement_id": "req_001"},
        }
        MockGraph.return_value = mock_graph

        response = client.post(
            f"/api/clarifications/requirements/req_001/kickoff?workspace={workspace}",
            json={"session_id": session_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"].startswith("proj_")
    assert data["requirement_id"] == "req_001"
    assert data["status"] == "kickoff_complete"
