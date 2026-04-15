from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from studio.runtime.poller import WorkflowPoller
from studio.schemas.design_doc import DesignDoc
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


@pytest.fixture
def workspace(tmp_path: Path) -> StudioWorkspace:
    ws = StudioWorkspace(tmp_path / ".studio-data")
    ws.ensure_layout()
    return ws


@pytest.fixture
def poller(tmp_path: Path) -> WorkflowPoller:
    return WorkflowPoller(
        workspace_path=tmp_path / ".studio-data",
        interval=1,
    )


def test_tick_picks_up_draft_requirement(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should find draft requirements and execute them."""
    req = RequirementCard(id="req_1", title="Test Game")
    workspace.requirements.save(req)

    with (
        patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor,
    ):
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        poller._tick()

    mock_executor.run.assert_called_once()
    assert mock_executor.run.call_args[1]["workspace_root"] == str(tmp_path / ".studio-data")


def test_tick_skips_non_draft_requirements(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should not pick up requirements that are not draft."""
    req = RequirementCard(id="req_1", title="Test Game", status="approved")
    workspace.requirements.save(req)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        MockExecutor.return_value = mock_executor

        poller._tick()

    mock_executor.run.assert_not_called()


def test_tick_picks_up_sent_back_rework(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should find designing requirements with sent_back design docs."""
    req = RequirementCard(
        id="req_1",
        title="Test Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Design",
        summary="Summary",
        status="sent_back",
        sent_back_reason="Needs work",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "requirement_id": "req_1",
            "design_doc_id": "design_1",
        }
        MockExecutor.return_value = mock_executor

        poller._tick()

    mock_executor.run.assert_called_once()


def test_tick_skips_designing_without_sent_back_doc(
    tmp_path: Path, workspace: StudioWorkspace, poller: WorkflowPoller
):
    """Poller should skip designing requirements whose design doc is not sent_back."""
    req = RequirementCard(
        id="req_1",
        title="Test Game",
        status="designing",
        design_doc_id="design_1",
    )
    workspace.requirements.save(req)
    doc = DesignDoc(
        id="design_1",
        requirement_id="req_1",
        title="Design",
        summary="Summary",
        status="pending_user_review",
    )
    workspace.design_docs.save(doc)

    with patch("studio.runtime.poller.DesignWorkflowExecutor") as MockExecutor:
        mock_executor = MagicMock()
        MockExecutor.return_value = mock_executor

        poller._tick()

    mock_executor.run.assert_not_called()
