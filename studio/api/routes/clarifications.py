from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter
from studio.llm import ClaudeRoleError
from studio.schemas.clarification import (
    ClarificationMessage,
    MeetingContextDraft,
    ReadinessCheck,
    RequirementClarificationSession,
)
from studio.storage.kickoff_service import KickoffService
from studio.storage.session_registry import SessionRegistry
from studio.storage.workspace import StudioWorkspace

router = APIRouter(prefix="/clarifications", tags=["clarifications"])

_SUPPORTED_ATTENDEES = {"design", "art", "dev", "qa"}
_CLARIFICATION_TIMEOUT_SECONDS = 45


class SendMessageRequest(BaseModel):
    message: str
    session_id: str


class KickoffRequest(BaseModel):
    session_id: str


def _get_workspace(workspace: str) -> StudioWorkspace:
    return StudioWorkspace(resolve_workspace_root(workspace))


def _validate_readiness(context: MeetingContextDraft) -> ReadinessCheck:
    missing: list[str] = []
    notes: list[str] = []
    if not context.summary or context.summary == "pending":
        missing.append("summary")
    if not context.goals:
        missing.append("goals")
    if not context.acceptance_criteria:
        missing.append("acceptance_criteria")
    if not context.risks:
        notes.append("No risks identified.")
    return ReadinessCheck(ready=len(missing) == 0, missing_fields=missing, notes=notes)


def _find_existing_session(store: StudioWorkspace, requirement_id: str):
    matches = [
        session
        for session in store.clarifications.list_all()
        if session.requirement_id == requirement_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda session: session.updated_at)


@router.post("/requirements/{req_id}/session")
async def start_or_get_session(workspace: str, req_id: str):
    store = _get_workspace(workspace)
    store.ensure_layout()
    try:
        store.requirements.get(req_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Requirement not found")

    existing = _find_existing_session(store, req_id)
    if existing:
        return {"session": existing.model_dump()}

    session = RequirementClarificationSession(
        id=f"clar_{req_id}",
        requirement_id=req_id,
    )
    saved = store.clarifications.save(session)
    return {"session": saved.model_dump()}


@router.post("/requirements/{req_id}/messages")
async def send_message(workspace: str, req_id: str, request: SendMessageRequest):
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message must not be empty")

    store = _get_workspace(workspace)
    try:
        session = store.clarifications.get(request.session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("collecting", "ready", "failed"):
        raise HTTPException(status_code=400, detail=f"Session is {session.status}")

    user_msg = ClarificationMessage(role="user", content=request.message.strip())
    session.messages.append(user_msg)
    session = session.model_copy(update={"updated_at": datetime.now(UTC).isoformat()})
    store.clarifications.save(session)

    try:
        profile = AgentProfileLoader().load("requirement_clarifier")
        adapter = ClaudeRoleAdapter(profile=profile, timeout_seconds=_CLARIFICATION_TIMEOUT_SECONDS)
        history = [{"role": m.role, "content": m.content} for m in session.messages]
        payload = await run_in_threadpool(
            adapter.generate,
            "requirement_clarifier",
            {
                "requirement_id": req_id,
                "conversation": history,
                "current_context": session.meeting_context.model_dump() if session.meeting_context else {},
            },
        )
    except Exception as exc:
        session = session.model_copy(update={"status": "failed", "updated_at": datetime.now(UTC).isoformat()})
        store.clarifications.save(session)
        raise HTTPException(status_code=502, detail=f"Clarification agent failed: {exc}")

    reply_text = str(payload.reply)
    assistant_msg = ClarificationMessage(role="assistant", content=reply_text)
    session.messages.append(assistant_msg)

    raw = payload.meeting_context if isinstance(payload.meeting_context, dict) else {}
    draft = MeetingContextDraft(
        summary=str(raw.get("summary", getattr(session.meeting_context, "summary", "pending") if session.meeting_context else "pending")),
        goals=[str(g) for g in raw.get("goals", [])],
        constraints=[str(c) for c in raw.get("constraints", [])],
        open_questions=[str(q) for q in raw.get("open_questions", [])],
        acceptance_criteria=[str(a) for a in raw.get("acceptance_criteria", [])],
        risks=[str(r) for r in raw.get("risks", [])],
        references=[str(ref) for ref in raw.get("references", [])],
        validated_attendees=[a for a in raw.get("validated_attendees", []) if a in _SUPPORTED_ATTENDEES],
    )

    readiness = _validate_readiness(draft)
    session = session.model_copy(update={
        "meeting_context": draft,
        "readiness": readiness,
        "status": "ready" if readiness.ready else "collecting",
        "updated_at": datetime.now(UTC).isoformat(),
    })
    store.clarifications.save(session)

    return {"session": session.model_dump(), "assistant_message": reply_text}


@router.post("/requirements/{req_id}/kickoff")
async def start_kickoff(workspace: str, req_id: str, request: KickoffRequest):
    store = _get_workspace(workspace)
    try:
        session = store.clarifications.get(request.session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    if not session.meeting_context or not session.readiness or not session.readiness.ready:
        missing = session.readiness.missing_fields if session.readiness else ["unknown"]
        raise HTTPException(status_code=400, detail=f"Session not ready for kickoff. Missing: {', '.join(missing)}")

    for a in session.meeting_context.validated_attendees:
        if a not in _SUPPORTED_ATTENDEES:
            raise HTTPException(status_code=400, detail=f"Unsupported attendee: {a}")

    session = session.model_copy(update={"status": "kickoff_started", "updated_at": datetime.now(UTC).isoformat()})
    store.clarifications.save(session)

    ws_root = resolve_workspace_root(workspace)
    service = KickoffService(ws_root, project_root=resolve_project_root(workspace))
    task = service.start_kickoff(
        workspace=workspace,
        session_id=request.session_id,
        requirement_id=req_id,
        meeting_context=session.meeting_context.model_dump(),
    )

    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "status": "kickoff_started",
    }


@router.get("/kickoff-tasks/{task_id}")
async def get_kickoff_task(task_id: str, workspace: str):
    ws_root = resolve_workspace_root(workspace)
    service = KickoffService(ws_root, project_root=resolve_project_root(workspace))
    try:
        task = service.get_task(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()
