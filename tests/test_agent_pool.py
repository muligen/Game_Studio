from __future__ import annotations


def test_pool_active_count_returns_to_zero_after_task_finishes() -> None:
    from studio.runtime import pool

    future = pool.submit_agent("dev", "req_001", "Implement task", lambda: "ok")

    assert future.result(timeout=5) == "ok"

    status = pool.status()
    assert status["idle"] is True
    assert status["tasks"] == []
    assert status["active_count"] == 0
