import pytest
from pydantic import ValidationError
from studio.schemas.meeting import AgentOpinion, MeetingMinutes


def test_agent_opinion_requires_role_and_summary():
    opinion = AgentOpinion(agent_role="design", summary="Looks good")
    assert opinion.agent_role == "design"
    assert opinion.proposals == []
    assert opinion.risks == []
    assert opinion.open_questions == []


def test_agent_opinion_rejects_empty_role():
    with pytest.raises(ValidationError):
        AgentOpinion(agent_role="", summary="x")


def test_meeting_minutes_basic():
    m = MeetingMinutes(
        id="meeting_abc",
        requirement_id="req_abc",
        title="Sprint Review",
        agenda=["Scope", "Tech"],
        attendees=["design", "dev"],
        opinions=[
            AgentOpinion(agent_role="design", summary="ok"),
            AgentOpinion(agent_role="dev", summary="risky"),
        ],
        consensus_points=["Use Unity"],
        conflict_points=["Timeline"],
        supplementary={},
        decisions=["Start with MVP"],
        action_items=["Create tasks"],
        pending_user_decisions=["Approve budget"],
    )
    assert m.status == "draft"
    assert len(m.opinions) == 2


def test_meeting_minutes_rejects_extra_fields():
    with pytest.raises(ValidationError):
        MeetingMinutes(
            id="meeting_abc",
            requirement_id="req_abc",
            title="Review",
            agenda=[],
            attendees=[],
            opinions=[],
            consensus_points=[],
            conflict_points=[],
            supplementary={},
            decisions=[],
            action_items=[],
            pending_user_decisions=[],
            unknown_field="oops",
        )
