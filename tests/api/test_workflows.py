from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def client():
    with patch("studio.api.main.DeliveryTaskPoller"):
        from studio.api.main import create_app
        app = create_app()
        return TestClient(app)


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


def test_run_design_uses_executor(client, tmp_path: Path, workspace: StudioWorkspace):
    """run-design endpoint should delegate to DesignWorkflowExecutor."""
    req = RequirementCard(id="req_1", title="Test Game")
    workspace.requirements.save(req)

    with patch("studio.runtime.executor.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        response = client.post(
            "/api/workflows/run-design",
            params={"workspace": str(tmp_path), "requirement_id": "req_1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["requirement_id"] == "req_1"
    assert data["design_doc_id"] == "design_1"
