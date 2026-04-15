from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from studio.api.main import create_app
from studio.schemas.balance_table import BalanceTable
from studio.schemas.design_doc import DesignDoc
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


def test_run_design_workflow(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/workflows/run-design should trigger design workflow."""
    req = RequirementCard(id="req_001", title="Test")
    temp_workspace.requirements.save(req)

    response = test_client.post(
        f"/api/workflows/run-design?workspace={get_workspace_param(workspace_path)}&requirement_id=req_001"
    )
    assert response.status_code == 200
    data = response.json()
    assert "design_doc_id" in data
    assert data["requirement_id"] == "req_001"
    assert data["requirement_status"] == "pending_user_review"
    assert data["design_doc_status"] == "pending_user_review"


def test_run_dev_workflow(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/workflows/run-dev should trigger dev workflow."""
    # Setup: create requirement with approved design doc
    req = RequirementCard(id="req_002", title="Dev Test", status="approved", design_doc_id="design_002")
    temp_workspace.requirements.save(req)

    design_doc = DesignDoc(
        id="design_002",
        requirement_id="req_002",
        title="Dev Test Design",
        summary="Design for dev test",
        status="approved",
    )
    temp_workspace.design_docs.save(design_doc)

    response = test_client.post(
        f"/api/workflows/run-dev?workspace={get_workspace_param(workspace_path)}&requirement_id=req_002"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requirement_id"] == "req_002"
    assert data["status"] == "self_test_passed"


def test_run_qa_workflow_success(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/workflows/run-qa should pass QA and go to user acceptance."""
    req = RequirementCard(id="req_003", title="QA Test", status="self_test_passed")
    temp_workspace.requirements.save(req)

    response = test_client.post(
        f"/api/workflows/run-qa?workspace={get_workspace_param(workspace_path)}&requirement_id=req_003&fail=false"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requirement_id"] == "req_003"
    assert data["status"] == "pending_user_acceptance"
    assert "bug_id" not in data


def test_run_qa_workflow_failure(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/workflows/run-qa with fail=true should create bug and go back to implementing."""
    req = RequirementCard(id="req_004", title="QA Fail Test", status="self_test_passed")
    temp_workspace.requirements.save(req)

    response = test_client.post(
        f"/api/workflows/run-qa?workspace={get_workspace_param(workspace_path)}&requirement_id=req_004&fail=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["requirement_id"] == "req_004"
    assert data["status"] == "implementing"
    assert "bug_id" in data
    assert data["bug_id"].startswith("bug_")


def test_run_dev_workflow_validation_failure(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/workflows/run-dev should return 400 when validation fails."""
    # Setup: create requirement without approved design doc
    req = RequirementCard(id="req_005", title="Validation Fail", status="approved", design_doc_id="design_005")
    temp_workspace.requirements.save(req)

    design_doc = DesignDoc(
        id="design_005",
        requirement_id="req_005",
        title="Unapproved Design",
        summary="Design not approved",
        status="pending_user_review",  # Not approved
    )
    temp_workspace.design_docs.save(design_doc)

    response = test_client.post(
        f"/api/workflows/run-dev?workspace={get_workspace_param(workspace_path)}&requirement_id=req_005"
    )
    assert response.status_code == 400
    assert "must be approved" in response.json()["detail"].lower()

