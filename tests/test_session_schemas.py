from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.session import ProjectAgentSession


def test_session_requires_project_id_agent_session_id():
    s = ProjectAgentSession(
        project_id="proj_123",
        requirement_id="req_456",
        agent="qa",
        session_id="claude-session-abc",
    )
    assert s.project_id == "proj_123"
    assert s.agent == "qa"
    assert s.session_id == "claude-session-abc"
    assert s.status == "active"


def test_session_rejects_empty_project_id():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="",
            requirement_id="req_1",
            agent="dev",
            session_id="sid",
        )


def test_session_rejects_empty_agent():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="",
            session_id="sid",
        )


def test_session_rejects_empty_session_id():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="dev",
            session_id="",
        )


def test_session_id_defaults_to_project_agent():
    s = ProjectAgentSession(
        project_id="proj_abc",
        requirement_id="req_1",
        agent="design",
        session_id="sid-1",
    )
    assert s.id == "proj_abc_design"


def test_session_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProjectAgentSession(
            project_id="proj_1",
            requirement_id="req_1",
            agent="dev",
            session_id="sid",
            unknown="oops",
        )


def test_session_created_at_is_auto_set():
    s = ProjectAgentSession(
        project_id="proj_1",
        requirement_id="req_1",
        agent="dev",
        session_id="sid",
    )
    assert s.created_at is not None
    assert s.last_used_at is not None
