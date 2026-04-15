# tests/api/test_logs.py
from pathlib import Path

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from studio.api.main import create_app
from studio.storage.workspace import StudioWorkspace


def test_list_logs(tmp_path: Path) -> None:
    """GET /api/logs should return list of action logs."""
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    workspace.ensure_layout()

    log = workspace.logs.new(
        actor="user",
        action="test",
        target_type="requirement",
        target_id="req_001",
        message="test log",
        metadata={},
    )
    workspace.logs.save(log)

    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/logs?workspace={tmp_path}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["action"] == "test"
