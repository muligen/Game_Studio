from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from studio.api.workspace_paths import resolve_workspace_root
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.meeting_transcript import MeetingTranscript
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _get_workspace(workspace: str) -> StudioWorkspace:
    workspace_path = resolve_workspace_root(workspace)
    return StudioWorkspace(workspace_path)


@router.get("")
async def list_meetings(workspace: str) -> list[MeetingMinutes]:
    store = _get_workspace(workspace)
    return store.meetings.list_all()


@router.get("/{meeting_id}")
async def get_meeting(workspace: str, meeting_id: str) -> MeetingMinutes:
    store = _get_workspace(workspace)
    try:
        return store.meetings.get(meeting_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found")


@router.get("/{meeting_id}/transcript")
async def get_meeting_transcript(workspace: str, meeting_id: str) -> MeetingTranscript:
    store = _get_workspace(workspace)
    try:
        return store.meeting_transcripts.get(meeting_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting transcript not found")
