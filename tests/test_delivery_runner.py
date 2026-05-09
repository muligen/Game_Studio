from __future__ import annotations

import threading
from pathlib import Path

from studio.runtime.delivery_runner import submit_delivery_plan


def test_submit_delivery_plan_reuses_alive_runner_for_same_plan(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def _runner(workspace_root: Path, project_root: Path, plan_id: str) -> None:
        _ = workspace_root, project_root
        calls.append(plan_id)
        started.set()
        release.wait(timeout=5)

    first = submit_delivery_plan(tmp_path, tmp_path, "plan_001", runner=_runner)
    assert started.wait(timeout=1)

    second = submit_delivery_plan(tmp_path, tmp_path, "plan_001", runner=_runner)

    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert second is first
    assert calls == ["plan_001"]

