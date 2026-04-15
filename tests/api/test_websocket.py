"""Tests for WebSocket endpoint."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.api.main import create_app


@pytest.mark.asyncio
async def test_websocket_connection() -> None:
    """WebSocket connection should be accepted."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "connected"


def test_websocket_broadcasts_requirement_changes(tmp_path: Path) -> None:
    """Mutating requirements through the API should broadcast entity updates."""
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"

        websocket.send_json({
            "type": "subscribe",
            "workspace": str(tmp_path),
        })
        subscribed = websocket.receive_json()
        assert subscribed["type"] == "subscribed"

        response = client.post(
            f"/api/requirements?workspace={tmp_path}",
            json={"title": "Broadcast me", "priority": "medium"},
        )
        assert response.status_code == 200
        created = response.json()

        message = websocket.receive_json()
        assert message == {
            "type": "entity_changed",
            "entity_type": "requirement",
            "entity_id": created["id"],
            "workspace": str(tmp_path),
            "action": "created",
        }
