from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from studio.api.main import create_app
from studio.schemas.bug import BugCard
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


def test_list_bugs_returns_empty_list(workspace_path: Path, test_client: TestClient):
    """GET /api/bugs should return empty list for new workspace."""
    response = test_client.get(f"/api/bugs?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_bugs_with_data(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/bugs should return existing bugs."""
    # Create multiple test bugs
    bug1 = BugCard(
        id="bug_001",
        requirement_id="req_001",
        title="First Bug",
        severity="high",
        owner="qa_agent",
    )
    bug2 = BugCard(
        id="bug_002",
        requirement_id="req_002",
        title="Second Bug",
        severity="medium",
        owner="qa_agent",
    )
    temp_workspace.bugs.save(bug1)
    temp_workspace.bugs.save(bug2)

    response = test_client.get(f"/api/bugs?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = [bug["title"] for bug in data]
    assert "First Bug" in titles
    assert "Second Bug" in titles


def test_create_bug(workspace_path: Path, test_client: TestClient):
    """POST /api/bugs should create a new bug."""
    response = test_client.post(
        f"/api/bugs?workspace={get_workspace_param(workspace_path)}",
        json={
            "requirement_id": "req_001",
            "title": "New Bug",
            "severity": "critical",
            "owner": "qa_agent",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Bug"
    assert data["severity"] == "critical"
    assert data["status"] == "new"
    assert data["requirement_id"] == "req_001"
    assert data["owner"] == "qa_agent"
    assert "id" in data
    assert data["id"].startswith("bug_")


def test_create_bug_default_owner(workspace_path: Path, test_client: TestClient):
    """POST /api/bugs should use default owner if not specified."""
    response = test_client.post(
        f"/api/bugs?workspace={get_workspace_param(workspace_path)}",
        json={
            "requirement_id": "req_001",
            "title": "Default Owner Bug",
            "severity": "low",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["owner"] == "qa_agent"


def test_get_bug_by_id(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/bugs/{id} should return a specific bug."""
    bug = BugCard(
        id="bug_get_test",
        requirement_id="req_001",
        title="Get Test Bug",
        severity="high",
        owner="qa_agent",
    )
    temp_workspace.bugs.save(bug)

    response = test_client.get(
        f"/api/bugs/bug_get_test?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "bug_get_test"
    assert data["title"] == "Get Test Bug"


def test_get_bug_not_found(workspace_path: Path, test_client: TestClient):
    """GET /api/bugs/{id} should return 404 for non-existent bug."""
    response = test_client.get(
        f"/api/bugs/bug_nonexistent?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_transition_bug_status(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """POST /api/bugs/{id}/transition should update bug status."""
    bug = BugCard(
        id="bug_transition",
        requirement_id="req_001",
        title="Transition Test",
        severity="high",
        owner="qa_agent",
        status="new",
    )
    temp_workspace.bugs.save(bug)

    response = test_client.post(
        f"/api/bugs/bug_transition/transition?workspace={get_workspace_param(workspace_path)}",
        json={"next_status": "fixing"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fixing"


def test_transition_bug_invalid_transition(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """POST /api/bugs/{id}/transition should return 400 for invalid transitions."""
    bug = BugCard(
        id="bug_invalid",
        requirement_id="req_001",
        title="Invalid Transition",
        severity="high",
        owner="qa_agent",
        status="new",
    )
    temp_workspace.bugs.save(bug)

    response = test_client.post(
        f"/api/bugs/bug_invalid/transition?workspace={get_workspace_param(workspace_path)}",
        json={"next_status": "closed"},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()
