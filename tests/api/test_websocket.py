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
