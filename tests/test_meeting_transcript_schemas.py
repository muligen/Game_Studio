import pytest
from pydantic import ValidationError

from studio.schemas.meeting_transcript import MeetingTranscript, MeetingTranscriptEvent


def test_meeting_transcript_event_requires_role_node_and_message() -> None:
    event = MeetingTranscriptEvent(
        sequence=1,
        agent_role="design",
        node_name="agent_opinion",
        kind="llm",
        message="Design proposes a cleaner puzzle loop.",
    )

    assert event.sequence == 1
    assert event.agent_role == "design"
    assert event.node_name == "agent_opinion"
    assert event.kind == "llm"
    assert event.prompt is None
    assert event.context == {}
    assert event.reply is None


def test_meeting_transcript_defaults_to_empty_events() -> None:
    transcript = MeetingTranscript(
        id="meeting_001",
        meeting_id="meeting_001",
        requirement_id="req_001",
        project_id="proj_001",
    )

    assert transcript.project_id == "proj_001"
    assert transcript.events == []


def test_meeting_transcript_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        MeetingTranscript(
            id="meeting_001",
            meeting_id="meeting_001",
            requirement_id="req_001",
            events=[],
            extra_field="nope",
        )
