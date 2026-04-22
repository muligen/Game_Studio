from __future__ import annotations

from pathlib import Path

import pytest

from studio.schemas.session import ProjectAgentSession
from studio.storage.session_registry import SessionRegistry


def test_create_stores_session(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    s = registry.create("proj_1", "req_1", "dev", "session-abc")
    assert s.project_id == "proj_1"
    assert s.agent == "dev"
    assert s.session_id == "session-abc"
    assert s.status == "active"


def test_create_persists_to_disk(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "dev", "session-abc")
    loaded = registry.find("proj_1", "dev")
    assert loaded is not None
    assert loaded.session_id == "session-abc"


def test_find_returns_none_when_missing(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    assert registry.find("proj_999", "qa") is None


def test_find_returns_session_when_exists(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "qa", "session-xyz")
    found = registry.find("proj_1", "qa")
    assert found is not None
    assert found.session_id == "session-xyz"


def test_touch_updates_last_used_at(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    registry.create("proj_1", "req_1", "dev", "session-abc")
    original = registry.find("proj_1", "dev")
    assert original is not None
    import time
    time.sleep(0.01)
    registry.touch("proj_1", "dev")
    updated = registry.find("proj_1", "dev")
    assert updated is not None
    assert updated.last_used_at != original.last_used_at


def test_touch_raises_when_missing(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    with pytest.raises(FileNotFoundError, match="project agent session not found"):
        registry.touch("proj_999", "qa")


def test_create_all_agents_creates_one_per_managed_agent(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    managed_agents = ["moderator", "design", "dev", "qa", "quality", "art", "reviewer"]
    sessions = registry.create_all("proj_1", "req_1", managed_agents)
    assert len(sessions) == 7
    for agent in managed_agents:
        found = registry.find("proj_1", agent)
        assert found is not None
        assert found.agent == agent


def test_create_all_agents_uses_unique_session_ids(tmp_path: Path):
    registry = SessionRegistry(tmp_path)
    managed_agents = ["moderator", "design", "dev"]
    sessions = registry.create_all("proj_1", "req_1", managed_agents)
    session_ids = [s.session_id for s in sessions]
    assert len(set(session_ids)) == len(session_ids)
