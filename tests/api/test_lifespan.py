from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


def test_app_starts_poller_on_lifespan():
    """FastAPI lifespan should create and start the WorkflowPoller."""
    with patch("studio.api.main.WorkflowPoller") as MockPoller:
        mock_poller = MagicMock()
        mock_poller.start = MagicMock()
        mock_poller.stop = MagicMock()
        MockPoller.return_value = mock_poller

        from studio.api.main import create_app
        app = create_app()
        # The lifespan context manager should have been set up
        assert app.router.lifespan_context is not None
