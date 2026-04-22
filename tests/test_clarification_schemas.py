from __future__ import annotations

import pytest
from pydantic import ValidationError

from studio.schemas.clarification import (
    ClarificationMessage,
    MeetingContextDraft,
    ReadinessCheck,
    RequirementClarificationSession,
)


def test_clarification_message_requires_role_and_content():
    msg = ClarificationMessage(role="user", content="I want combat.")
    assert msg.role == "user"
    assert msg.created_at is not None


def test_clarification_message_rejects_empty_role():
    with pytest.raises(ValidationError):
        ClarificationMessage(role="", content="hello")


def test_clarification_message_rejects_empty_content():
    with pytest.raises(ValidationError):
        ClarificationMessage(role="user", content="")


def test_meeting_context_draft_defaults():
    ctx = MeetingContextDraft(summary="A combat system")
    assert ctx.summary == "A combat system"
    assert ctx.goals == []
    assert ctx.constraints == []
    assert ctx.open_questions == []
    assert ctx.acceptance_criteria == []
    assert ctx.risks == []
    assert ctx.references == []
    assert ctx.validated_attendees == []


def test_meeting_context_draft_rejects_unknown_attendees():
    with pytest.raises(ValidationError):
        MeetingContextDraft(
            summary="test",
            validated_attendees=["design", "producer"],
        )


def test_readiness_check_requires_ready_and_missing_fields():
    r = ReadinessCheck(ready=False, missing_fields=["acceptance_criteria"])
    assert r.ready is False
    assert r.missing_fields == ["acceptance_criteria"]
    assert r.notes == []


def test_session_basic():
    s = RequirementClarificationSession(
        id="clar_req_001",
        requirement_id="req_001",
        status="collecting",
    )
    assert s.status == "collecting"
    assert s.messages == []
    assert s.meeting_context is None
    assert s.project_id is None
    assert s.created_at is not None


def test_session_status_values():
    for status in ("collecting", "ready", "kickoff_started", "completed", "failed"):
        s = RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status=status,
        )
        assert s.status == status


def test_session_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status="unknown",
        )


def test_session_rejects_extra_fields():
    with pytest.raises(ValidationError):
        RequirementClarificationSession(
            id="clar_1",
            requirement_id="req_1",
            status="collecting",
            extra="oops",
        )
