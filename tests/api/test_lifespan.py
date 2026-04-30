from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_app_lifespan_shutdown_does_not_start_legacy_delivery_poller():
    events: list[str] = []

    with (
        patch("studio.api.main.KickoffService"),
        patch("studio.api.main.process_registry") as mock_registry,
        patch("studio.api.main.pool") as mock_pool,
    ):
        def kill_all(*, reason: str):
            events.append(f"kill_all:{reason}")
            return {"attempted": 0, "already_exited": 0, "failed": 0}

        def shutdown(*, wait: bool = True):
            events.append(f"pool_shutdown:{wait}")

        mock_registry.kill_all.side_effect = kill_all
        mock_pool.shutdown.side_effect = shutdown

        from studio.api.main import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/api/health").json() == {"status": "ok"}

    assert "delivery_start" not in events
    assert "delivery_stop" not in events
    assert events.index("kill_all:server_shutdown") < events.index("pool_shutdown:False")
