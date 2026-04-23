from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from studio.storage.session_lease import SessionLeaseManager


@pytest.fixture()
def manager(tmp_path: Path) -> SessionLeaseManager:
    return SessionLeaseManager(tmp_path)


class TestAcquire:
    def test_acquire_returns_held_lease(self, manager: SessionLeaseManager) -> None:
        lease = manager.acquire("proj_1", "coder", "task_1", "sess_abc")

        assert lease.status == "held"
        assert lease.project_id == "proj_1"
        assert lease.agent == "coder"
        assert lease.task_id == "task_1"
        assert lease.session_id == "sess_abc"
        assert lease.id == "proj_1_coder"

    def test_acquire_persists_to_disk(self, manager: SessionLeaseManager, tmp_path: Path) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")

        json_file = tmp_path / "agent_session_leases" / "proj_1_coder.json"
        assert json_file.exists()

        # Round-trip through the repo to verify persistence
        found = manager.find("proj_1", "coder")
        assert found is not None
        assert found.status == "held"
        assert found.task_id == "task_1"

    def test_acquire_fails_when_already_held(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")

        with pytest.raises(ValueError, match="session lease already held by task task_1"):
            manager.acquire("proj_1", "coder", "task_2", "sess_def")


class TestRelease:
    def test_release_marks_lease_as_released(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")
        released = manager.release("proj_1", "coder")

        assert released.status == "released"
        assert released.project_id == "proj_1"
        assert released.agent == "coder"

    def test_release_allows_re_acquire(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")
        manager.release("proj_1", "coder")

        lease = manager.acquire("proj_1", "coder", "task_2", "sess_def")
        assert lease.status == "held"
        assert lease.task_id == "task_2"
        assert lease.session_id == "sess_def"

    def test_release_nonexistent_raises_file_not_found(self, manager: SessionLeaseManager) -> None:
        with pytest.raises(FileNotFoundError, match="no lease for proj_1_coder"):
            manager.release("proj_1", "coder")


class TestIsAvailable:
    def test_available_when_no_lease(self, manager: SessionLeaseManager) -> None:
        assert manager.is_available("proj_1", "coder") is True

    def test_not_available_when_held(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")

        assert manager.is_available("proj_1", "coder") is False

    def test_available_when_released(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")
        manager.release("proj_1", "coder")

        assert manager.is_available("proj_1", "coder") is True


class TestFind:
    def test_find_returns_none_when_no_lease(self, manager: SessionLeaseManager) -> None:
        assert manager.find("proj_1", "coder") is None

    def test_find_returns_lease_after_acquire(self, manager: SessionLeaseManager) -> None:
        manager.acquire("proj_1", "coder", "task_1", "sess_abc")
        lease = manager.find("proj_1", "coder")

        assert lease is not None
        assert lease.id == "proj_1_coder"
        assert lease.status == "held"


class TestExpiredLease:
    def test_expired_lease_auto_releases_on_is_available(self, manager: SessionLeaseManager) -> None:
        from studio.schemas.delivery import AgentSessionLease
        expired_lease = AgentSessionLease(
            project_id="proj_1",
            agent="coder",
            task_id="task_1",
            session_id="sess_abc",
            expires_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        )
        manager._repo.save(expired_lease)
        assert manager.is_available("proj_1", "coder") is True
        # Verify it was actually released
        lease = manager.find("proj_1", "coder")
        assert lease is not None
        assert lease.status == "released"

    def test_expired_lease_auto_releases_on_acquire(self, manager: SessionLeaseManager) -> None:
        from studio.schemas.delivery import AgentSessionLease
        expired_lease = AgentSessionLease(
            project_id="proj_1",
            agent="coder",
            task_id="task_old",
            session_id="sess_old",
            expires_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        )
        manager._repo.save(expired_lease)
        # Should succeed — expired lease is auto-released
        new_lease = manager.acquire("proj_1", "coder", "task_new", "sess_new")
        assert new_lease.task_id == "task_new"
