from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_app_lifespan_shutdown_only_runs_delivery_task_poller():
    events: list[str] = []

    with (
        patch("studio.api.main.DeliveryTaskPoller") as MockDeliveryTaskPoller,
        patch("studio.api.main.KickoffService"),
        patch("studio.api.main.process_registry") as mock_registry,
        patch("studio.api.main.pool") as mock_pool,
    ):
        delivery_poller = MagicMock()

        async def delivery_start():
            events.append("delivery_start")

        async def delivery_stop():
            events.append("delivery_stop")

        delivery_poller.start = delivery_start
        delivery_poller.stop = delivery_stop
        MockDeliveryTaskPoller.return_value = delivery_poller

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

    assert events.count("delivery_start") == 1
    assert "delivery_stop" in events
    assert events.index("kill_all:server_shutdown") < events.index("pool_shutdown:False")
