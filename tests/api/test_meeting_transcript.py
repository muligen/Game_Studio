from pathlib import Path

from fastapi.testclient import TestClient

from studio.api.main import create_app
from studio.schemas.meeting_transcript import MeetingTranscript, MeetingTranscriptEvent
from studio.storage.workspace import StudioWorkspace


def _seed_transcript(workspace: Path) -> None:
    store = StudioWorkspace(workspace / ".studio-data")
    store.ensure_layout()
    store.meeting_transcripts.save(
        MeetingTranscript(
            id="meeting_001",
            meeting_id="meeting_001",
            requirement_id="req_001",
            events=[
                MeetingTranscriptEvent(
                    sequence=1,
                    agent_role="moderator",
                    node_name="moderator_prepare",
                    kind="llm",
                    message="Prepared agenda",
                    prompt="prepare prompt",
                    context={"prompt": "Design a puzzle game"},
                    reply={"agenda": ["Scope"]},
                )
            ],
        )
    )


def test_get_meeting_transcript_returns_transcript(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _seed_transcript(workspace)
    client = TestClient(create_app())

    response = client.get(
        "/api/meetings/meeting_001/transcript",
        params={"workspace": str(workspace)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meeting_id"] == "meeting_001"
    assert data["events"][0]["agent_role"] == "moderator"
    assert data["events"][0]["prompt"] == "prepare prompt"


def test_get_meeting_transcript_returns_404_for_missing_transcript(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    StudioWorkspace(workspace / ".studio-data").ensure_layout()
    client = TestClient(create_app())

    response = client.get(
        "/api/meetings/missing/transcript",
        params={"workspace": str(workspace)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Meeting transcript not found"
