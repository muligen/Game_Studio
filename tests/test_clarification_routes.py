from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from studio.llm import ClaudeRoleError
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


def test_start_accepts_workspace_pointing_at_studio_data_dir(client, workspace):
    response = client.post(
        f"/api/clarifications/requirements/req_001/session?workspace={Path(workspace) / '.studio-data'}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session"]["requirement_id"] == "req_001"


def test_start_returns_existing_session(client, workspace):
    r1 = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    r2 = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    assert r1.json()["session"]["id"] == r2.json()["session"]["id"]


def test_start_returns_completed_session_instead_of_overwriting_history(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    session = ws.clarifications.get(session_id)
    session = session.model_copy(
        update={
            "status": "completed",
            "messages": [
                session.messages[0] if session.messages else None,
            ],
        }
    )
    session.messages = [message for message in session.messages if message is not None]
    if not session.messages:
        from studio.schemas.clarification import ClarificationMessage

        session.messages = [ClarificationMessage(role="assistant", content="history kept")]
    ws.clarifications.save(session)

    response = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")

    assert response.status_code == 200
    data = response.json()["session"]
    assert data["id"] == session_id
    assert data["status"] == "completed"
    assert len(data["messages"]) == 1


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


def test_send_message_runs_agent_in_threadpool(client, workspace, monkeypatch):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]
    calls: list[object] = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        calls.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "studio.api.routes.clarifications.run_in_threadpool",
        fake_run_in_threadpool,
    )

    with patch("studio.api.routes.clarifications.ClaudeRoleAdapter") as MockAdapter:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = type("Payload", (), {
            "reply": "Which platform should the snake game target?",
            "meeting_context": {
                "summary": "Snake game",
                "goals": [],
                "constraints": [],
                "open_questions": ["Target platform?"],
                "acceptance_criteria": [],
                "risks": [],
                "references": [],
                "validated_attendees": ["design"],
            },
        })()
        MockAdapter.return_value = mock_instance

        response = client.post(
            f"/api/clarifications/requirements/req_001/messages?workspace={workspace}",
            json={"message": "I want a snake game.", "session_id": session_id},
    )

    assert response.status_code == 200
    assert len(calls) == 1
    mock_instance.generate.assert_called_once()


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
         patch("studio.api.routes.clarifications.build_meeting_graph") as MockGraph, \
         patch("studio.api.routes.clarifications.DeliveryPlanService") as MockDeliveryPlanService:
        mock_reg = MagicMock()
        mock_reg.create_all.return_value = []
        MockRegistry.return_value = mock_reg

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "moderator_minutes",
            "minutes": {
                "id": "meeting_001",
                "requirement_id": "req_001",
                "title": "Kickoff: Combat system",
                "summary": "The team aligned on a compact combat MVP.",
                "attendees": ["design", "dev"],
                "consensus": ["Build one turn-based battle loop first."],
                "conflicts": ["Progression depth is postponed."],
                "pending_user_decisions": [],
            },
        }
        MockGraph.return_value = mock_graph
        MockDeliveryPlanService.return_value = MagicMock()

        response = client.post(
            f"/api/clarifications/requirements/req_001/kickoff?workspace={workspace}",
            json={"session_id": session_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"].startswith("proj_")
    assert data["requirement_id"] == "req_001"
    assert data["status"] == "kickoff_complete"
    assert data["meeting_id"] == "meeting_001"
    assert data["meeting"] == {
        "id": "meeting_001",
        "title": "Kickoff: Combat system",
        "summary": "The team aligned on a compact combat MVP.",
        "attendees": ["design", "dev"],
        "consensus_points": ["Build one turn-based battle loop first."],
        "conflict_points": ["Progression depth is postponed."],
        "pending_user_decisions": [],
    }


def test_kickoff_generates_delivery_plan_server_side(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    session = ws.clarifications.get(session_id)
    from studio.schemas.clarification import MeetingContextDraft, ReadinessCheck
    session = session.model_copy(update={
        "meeting_context": MeetingContextDraft(
            summary="Snake MVP",
            goals=["Build the first playable snake prototype"],
            acceptance_criteria=["Classic snake loop works"],
            risks=["Scope growth"],
            validated_attendees=["design", "dev", "qa"],
        ),
        "readiness": ReadinessCheck(ready=True, missing_fields=[]),
        "status": "ready",
    })
    ws.clarifications.save(session)

    with patch("studio.api.routes.clarifications.SessionRegistry") as MockRegistry, \
         patch("studio.api.routes.clarifications.build_meeting_graph") as MockGraph, \
         patch("studio.api.routes.clarifications.DeliveryPlanService") as MockDeliveryPlanService:
        mock_reg = MagicMock()
        mock_reg.create_all.return_value = []
        MockRegistry.return_value = mock_reg

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "moderator_minutes",
            "minutes": {
                "id": "meeting_002",
                "requirement_id": "req_001",
                "title": "Kickoff: Snake MVP",
                "summary": "The team aligned on a snake MVP.",
                "attendees": ["design", "dev", "qa"],
                "consensus": [],
                "conflicts": [],
                "pending_user_decisions": [],
            },
        }
        MockGraph.return_value = mock_graph

        delivery_service = MagicMock()
        MockDeliveryPlanService.return_value = delivery_service

        response = client.post(
            f"/api/clarifications/requirements/req_001/kickoff?workspace={workspace}",
            json={"session_id": session_id},
        )

    assert response.status_code == 200
    delivery_service.generate_plan.assert_called_once()
    assert delivery_service.generate_plan.call_args.kwargs == {
        "meeting_id": "meeting_002",
        "project_id": response.json()["project_id"],
    }


def test_kickoff_retries_transient_delivery_plan_failure(client, workspace):
    start = client.post(f"/api/clarifications/requirements/req_001/session?workspace={workspace}")
    session_id = start.json()["session"]["id"]

    ws = StudioWorkspace(Path(workspace) / ".studio-data")
    session = ws.clarifications.get(session_id)
    from studio.schemas.clarification import MeetingContextDraft, ReadinessCheck
    session = session.model_copy(update={
        "meeting_context": MeetingContextDraft(
            summary="Snake MVP",
            goals=["Build the first playable snake prototype"],
            acceptance_criteria=["Classic snake loop works"],
            risks=["Scope growth"],
            validated_attendees=["design"],
        ),
        "readiness": ReadinessCheck(ready=True, missing_fields=[]),
        "status": "ready",
    })
    ws.clarifications.save(session)

    with patch("studio.api.routes.clarifications.SessionRegistry") as MockRegistry, \
         patch("studio.api.routes.clarifications.build_meeting_graph") as MockGraph, \
         patch("studio.api.routes.clarifications.DeliveryPlanService") as MockDeliveryPlanService:
        MockRegistry.return_value.create_all.return_value = []
        MockGraph.return_value.invoke.return_value = {
            "node_name": "moderator_minutes",
            "minutes": {
                "id": "meeting_002",
                "requirement_id": "req_001",
                "title": "Kickoff: Snake MVP",
                "summary": "The team aligned on a snake MVP.",
                "attendees": ["design"],
                "consensus": [],
                "conflicts": [],
                "pending_user_decisions": [],
            },
        }
        delivery_service = MagicMock()
        delivery_service.generate_plan.side_effect = [ClaudeRoleError("invalid_claude_output"), MagicMock()]
        MockDeliveryPlanService.return_value = delivery_service

        response = client.post(
            f"/api/clarifications/requirements/req_001/kickoff?workspace={workspace}",
            json={"session_id": session_id},
        )

    assert response.status_code == 200
    assert delivery_service.generate_plan.call_count == 2
