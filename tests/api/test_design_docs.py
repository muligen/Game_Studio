from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from studio.api.main import create_app
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard, RequirementStatus
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
def temp_workspace_with_design(workspace_path: Path) -> StudioWorkspace:
    """Create a workspace with a design doc."""
    workspace = StudioWorkspace(workspace_path)
    workspace.ensure_layout()

    # Create requirement first
    req = RequirementCard(
        id="req_001",
        title="Test Requirement",
        status="designing",
    )
    workspace.requirements.save(req)

    # Create design doc
    design = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Test Design",
        summary="Test summary",
    )
    workspace.design_docs.save(design)
    return workspace


def get_workspace_param(workspace_path: Path) -> str:
    """Get workspace parameter for API calls."""
    return str(workspace_path.parent)


def test_list_design_docs(temp_workspace_with_design: StudioWorkspace, workspace_path: Path) -> None:
    """GET /api/design-docs should return list of design docs."""
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/design-docs?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == "design_001"


def test_list_design_docs_empty(workspace_path: Path) -> None:
    """GET /api/design-docs should return empty list for new workspace."""
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/design-docs?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_design_doc_by_id(temp_workspace_with_design: StudioWorkspace, workspace_path: Path) -> None:
    """GET /api/design-docs/{id} should return a specific design doc."""
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/design-docs/design_001?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "design_001"
    assert data["title"] == "Test Design"
    assert data["summary"] == "Test summary"


def test_get_design_doc_not_found(workspace_path: Path) -> None:
    """GET /api/design-docs/{id} should return 404 for non-existent design doc."""
    app = create_app()
    client = TestClient(app)

    response = client.get(f"/api/design-docs/design_nonexistent?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_design_doc(temp_workspace_with_design: StudioWorkspace, workspace_path: Path) -> None:
    """PATCH /api/design-docs/{id} should update a design doc."""
    app = create_app()
    client = TestClient(app)

    response = client.patch(
        f"/api/design-docs/design_001?workspace={get_workspace_param(workspace_path)}",
        json={"title": "Updated Title", "summary": "Updated summary"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "design_001"
    assert data["title"] == "Updated Title"
    assert data["summary"] == "Updated summary"


def test_update_design_doc_partial(temp_workspace_with_design: StudioWorkspace, workspace_path: Path) -> None:
    """PATCH /api/design-docs/{id} should support partial updates."""
    app = create_app()
    client = TestClient(app)

    response = client.patch(
        f"/api/design-docs/design_001?workspace={get_workspace_param(workspace_path)}",
        json={"title": "Only Title Updated"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Only Title Updated"
    assert data["summary"] == "Test summary"  # Unchanged


def test_approve_design_doc(temp_workspace: StudioWorkspace, workspace_path: Path) -> None:
    """POST /api/design-docs/{id}/approve should approve and transition requirement."""
    # Create requirement in pending_user_review status
    req = RequirementCard(
        id="req_approve",
        title="Test Requirement",
        status="pending_user_review",
        design_doc_id="design_approve",
    )
    temp_workspace.requirements.save(req)

    # Create design doc in pending_user_review status
    design = DesignDoc(
        id="design_approve",
        requirement_id="req_approve",
        title="Test Design",
        summary="Test summary",
        status="pending_user_review",
    )
    temp_workspace.design_docs.save(design)

    app = create_app()
    client = TestClient(app)

    response = client.post(f"/api/design-docs/design_approve/approve?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert "design_doc" in data
    assert "requirement" in data
    assert data["design_doc"]["status"] == "approved"
    assert data["requirement"]["status"] == "approved"


def test_approve_design_doc_invalid_status(temp_workspace: StudioWorkspace, workspace_path: Path) -> None:
    """POST /api/design-docs/{id}/approve should return 400 for invalid status."""
    req = RequirementCard(
        id="req_invalid",
        title="Test Requirement",
        status="designing",
    )
    temp_workspace.requirements.save(req)

    design = DesignDoc(
        id="design_invalid",
        requirement_id="req_invalid",
        title="Test Design",
        summary="Test summary",
        status="draft",  # Wrong status
    )
    temp_workspace.design_docs.save(design)

    app = create_app()
    client = TestClient(app)

    response = client.post(f"/api/design-docs/design_invalid/approve?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 400
    assert "must be pending_user_review" in response.json()["detail"]


def test_send_back_design_doc(temp_workspace: StudioWorkspace, workspace_path: Path) -> None:
    """POST /api/design-docs/{id}/send-back should send back for revision."""
    req = RequirementCard(
        id="req_sendback",
        title="Test Requirement",
        status="pending_user_review",
        design_doc_id="design_sendback",
    )
    temp_workspace.requirements.save(req)

    design = DesignDoc(
        id="design_sendback",
        requirement_id="req_sendback",
        title="Test Design",
        summary="Test summary",
        status="pending_user_review",
    )
    temp_workspace.design_docs.save(design)

    app = create_app()
    client = TestClient(app)

    response = client.post(
        f"/api/design-docs/design_sendback/send-back?workspace={get_workspace_param(workspace_path)}",
        json={"reason": "Needs more details"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "design_doc" in data
    assert "requirement" in data
    assert data["design_doc"]["status"] == "sent_back"
    assert data["requirement"]["status"] == "designing"

