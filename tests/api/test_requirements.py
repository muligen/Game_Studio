# tests/api/test_requirements.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from studio.api.main import create_app
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def workspace_path(tmp_path: Path) -> Path:
    """Create a temporary workspace path for testing."""
    return tmp_path / ".studio-data"


@pytest.fixture
def temp_workspace(workspace_path: Path) -> StudioWorkspace:
    """Create a temporary workspace for testing."""
    ws = StudioWorkspace(workspace_path)
    ws.ensure_layout()
    return ws


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for API testing."""
    app = create_app()
    return TestClient(app)


def get_workspace_param(workspace_path: Path) -> str:
    """Get workspace parameter for API calls."""
    return str(workspace_path.parent)


def test_list_requirements_returns_empty_list(workspace_path: Path, test_client: TestClient):
    """GET /api/requirements should return empty list for new workspace."""
    response = test_client.get(f"/api/requirements?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_requirements_with_data(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/requirements should return existing requirements."""
    # Create multiple test requirements
    req1 = RequirementCard(id="req_001", title="First Requirement")
    req2 = RequirementCard(id="req_002", title="Second Requirement")
    temp_workspace.requirements.save(req1)
    temp_workspace.requirements.save(req2)

    response = test_client.get(f"/api/requirements?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = [req["title"] for req in data]
    assert "First Requirement" in titles
    assert "Second Requirement" in titles


def test_create_requirement(workspace_path: Path, test_client: TestClient):
    """POST /api/requirements should create a new requirement."""
    response = test_client.post(
        f"/api/requirements?workspace={get_workspace_param(workspace_path)}",
        json={"title": "New Feature", "priority": "high"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Feature"
    assert data["priority"] == "high"
    assert data["status"] == "draft"
    assert "id" in data
    assert data["id"].startswith("req_")


def test_create_requirement_default_priority(workspace_path: Path, test_client: TestClient):
    """POST /api/requirements should use default priority if not specified."""
    response = test_client.post(
        f"/api/requirements?workspace={get_workspace_param(workspace_path)}",
        json={"title": "Default Priority Feature"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == "medium"


def test_get_requirement_by_id(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/requirements/{id} should return a specific requirement."""
    req = RequirementCard(id="req_get_test", title="Get Test Requirement")
    temp_workspace.requirements.save(req)

    response = test_client.get(
        f"/api/requirements/req_get_test?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "req_get_test"
    assert data["title"] == "Get Test Requirement"


def test_get_requirement_not_found(workspace_path: Path, test_client: TestClient):
    """GET /api/requirements/{id} should return 404 for non-existent requirement."""
    response = test_client.get(
        f"/api/requirements/req_nonexistent?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_transition_requirement_status(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """POST /api/requirements/{id}/transition should update requirement status."""
    req = RequirementCard(id="req_transition", title="Transition Test", status="draft")
    temp_workspace.requirements.save(req)

    response = test_client.post(
        f"/api/requirements/req_transition/transition?workspace={get_workspace_param(workspace_path)}",
        json={"next_status": "designing"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "designing"


def test_transition_requirement_invalid_transition(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """POST /api/requirements/{id}/transition should return 400 for invalid transitions."""
    req = RequirementCard(id="req_invalid", title="Invalid Transition", status="draft")
    temp_workspace.requirements.save(req)

    response = test_client.post(
        f"/api/requirements/req_invalid/transition?workspace={get_workspace_param(workspace_path)}",
        json={"next_status": "testing"},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()
