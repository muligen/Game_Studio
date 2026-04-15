from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from studio.runtime.executor import DesignWorkflowExecutor
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


def test_executor_new_design(tmp_path: Path, workspace: StudioWorkspace):
    """Executor should invoke design graph for a draft requirement."""
    req = RequirementCard(id="req_1", title="Garden Game")
    workspace.requirements.save(req)

    mock_result = {
        "node_name": "design",
        "requirement_id": "req_1",
        "design_doc_id": "design_1",
        "fallback_used": False,
    }
    with patch("studio.runtime.executor.build_design_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = mock_result
        mock_build.return_value = mock_graph

        executor = DesignWorkflowExecutor()
        result = executor.run(workspace, req, workspace_root=str(tmp_path))

    mock_graph.invoke.assert_called_once()
    assert result["requirement_id"] == "req_1"
    assert result["design_doc_id"] == "design_1"


def test_executor_rework(tmp_path: Path, workspace: StudioWorkspace):
    """Executor should pass sent_back_reason for a rework."""
    from studio.schemas.design_doc import DesignDoc

    req = RequirementCard(
        id="req_1",
        title="Garden Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Garden Design",
        summary="Summary",
        status="sent_back",
        sent_back_reason="Need more detail",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.executor.build_design_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "node_name": "design",
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        mock_build.return_value = mock_graph

        executor = DesignWorkflowExecutor()
        result = executor.run(workspace, req, workspace_root=str(tmp_path))

    call_input = mock_graph.invoke.call_args[0][0]
    assert call_input["requirement_id"] == "req_1"
