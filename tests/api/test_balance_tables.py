# tests/api/test_balance_tables.py
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from studio.api.main import create_app
from studio.schemas.balance_table import BalanceTable, BalanceTableRow
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


def test_list_balance_tables_returns_empty_list(workspace_path: Path, test_client: TestClient):
    """GET /api/balance-tables should return empty list for new workspace."""
    response = test_client.get(f"/api/balance-tables?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_balance_tables_with_data(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/balance-tables should return existing balance tables."""
    # Create multiple test balance tables
    table1 = BalanceTable(
        id="balance_001",
        requirement_id="req_001",
        table_name="First Table",
    )
    table2 = BalanceTable(
        id="balance_002",
        requirement_id="req_002",
        table_name="Second Table",
    )
    temp_workspace.balance_tables.save(table1)
    temp_workspace.balance_tables.save(table2)

    response = test_client.get(f"/api/balance-tables?workspace={get_workspace_param(workspace_path)}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = [table["table_name"] for table in data]
    assert "First Table" in names
    assert "Second Table" in names


def test_create_balance_table(workspace_path: Path, test_client: TestClient) -> None:
    """POST /api/balance-tables should create a new balance table."""
    response = test_client.post(
        "/api/balance-tables",
        params={
            "workspace": get_workspace_param(workspace_path),
            "requirement_id": "req_001",
            "table_name": "test_table",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "test_table"
    assert data["requirement_id"] == "req_001"


def test_create_balance_table_with_params(workspace_path: Path, test_client: TestClient):
    """POST /api/balance-tables should create a new balance table with query params."""
    response = test_client.post(
        f"/api/balance-tables?workspace={get_workspace_param(workspace_path)}&requirement_id=req_001&table_name=test_table",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "test_table"
    assert data["requirement_id"] == "req_001"
    assert "id" in data
    assert data["id"].startswith("balance_")


def test_get_balance_table_by_id(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """GET /api/balance-tables/{id} should return a specific balance table."""
    table = BalanceTable(
        id="balance_get_test",
        requirement_id="req_001",
        table_name="Get Test Table",
    )
    temp_workspace.balance_tables.save(table)

    response = test_client.get(
        f"/api/balance-tables/balance_get_test?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "balance_get_test"
    assert data["table_name"] == "Get Test Table"


def test_get_balance_table_not_found(workspace_path: Path, test_client: TestClient):
    """GET /api/balance-tables/{id} should return 404 for non-existent table."""
    response = test_client.get(
        f"/api/balance-tables/balance_nonexistent?workspace={get_workspace_param(workspace_path)}"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_balance_table_rows(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """PATCH /api/balance-tables/{id} should update table rows."""
    table = BalanceTable(
        id="balance_update",
        requirement_id="req_001",
        table_name="Update Test",
        columns=["col1", "col2"],
    )
    temp_workspace.balance_tables.save(table)

    new_rows = [
        {"values": {"col1": "value1", "col2": "value2"}},
        {"values": {"col1": "value3", "col2": "value4"}},
    ]
    # Use request body instead of query parameters
    response = test_client.patch(
        f"/api/balance-tables/balance_update?workspace={get_workspace_param(workspace_path)}",
        json={"rows": new_rows},
    )
    assert response.status_code == 200
    data = response.json()
    # Verify rows were actually updated
    assert len(data["rows"]) == 2
    assert data["rows"][0]["values"]["col1"] == "value1"
    assert data["rows"][0]["values"]["col2"] == "value2"
    assert data["rows"][1]["values"]["col1"] == "value3"
    assert data["rows"][1]["values"]["col2"] == "value4"


def test_update_balance_table_locked_cells(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """PATCH /api/balance-tables/{id} should update locked cells."""
    table = BalanceTable(
        id="balance_lock",
        requirement_id="req_001",
        table_name="Lock Test",
        columns=["col1", "col2"],
    )
    temp_workspace.balance_tables.save(table)

    locked_cells = ["cell1", "cell2"]
    # Use request body instead of query parameters
    response = test_client.patch(
        f"/api/balance-tables/balance_lock?workspace={get_workspace_param(workspace_path)}",
        json={"locked_cells": locked_cells},
    )
    assert response.status_code == 200
    data = response.json()
    # Verify locked cells were actually updated
    assert len(data["locked_cells"]) == 2
    assert "cell1" in data["locked_cells"]
    assert "cell2" in data["locked_cells"]


def test_update_balance_table_invalid_rows(temp_workspace: StudioWorkspace, workspace_path: Path, test_client: TestClient):
    """PATCH /api/balance-tables/{id} should return 400 for invalid row data."""
    table = BalanceTable(
        id="balance_invalid",
        requirement_id="req_001",
        table_name="Invalid Test",
        columns=["col1", "col2"],
    )
    temp_workspace.balance_tables.save(table)

    # Invalid row data (missing 'values' key)
    invalid_rows = [{"invalid": "data"}]
    # Use request body instead of query parameters
    response = test_client.patch(
        f"/api/balance-tables/balance_invalid?workspace={get_workspace_param(workspace_path)}",
        json={"rows": invalid_rows},
    )
    # Should return 400 due to validation error
    assert response.status_code == 400
    assert "detail" in response.json()
