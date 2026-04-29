from __future__ import annotations

from datetime import UTC, datetime
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.agents.profile_loader import AgentProfileLoader
from studio.llm import ClaudeRoleAdapter
from studio.schemas.clarification import (
    ClarificationMessage,
    MeetingContextDraft,
    ReadinessCheck,
    RequirementClarificationSession,
)
from studio.storage.kickoff_service import KickoffService
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


def _infer_validated_attendees(*texts: str) -> list[str]:
    supported = ("design", "art", "dev", "qa")
    combined = "\n".join(text.lower() for text in texts if text).strip()
    if not combined:
        return []

    patterns = (
        r"\b(design|art|dev|qa)\b(?:\s+will\s+be|\s+as)?\s+the\s+sole\s+attendee\b",
        r"\b(design|art|dev|qa)\b(?:\s+should\s+be|\s+as)?\s+the\s+only\s+meeting\s+attendee\b",
        r"\buse\s+(design|art|dev|qa)\s+as\s+the\s+only\s+meeting\s+attendee\b",
        r"\b(design|art|dev|qa)\s+only\b.*\battendee\b",
    )
    for pattern in patterns:
        match = re.search(pattern, combined, flags=re.IGNORECASE | re.DOTALL)
        if match:
            attendee = match.group(1).lower()
            if attendee in supported:
                return [attendee]
    return []


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

    # Transition requirement: draft → designing
    try:
        from studio.domain.requirement_flow import transition_requirement
        requirement = store.requirements.get(req_id)
        if requirement.status == "draft":
            requirement = transition_requirement(requirement, "designing")
            store.requirements.save(requirement)
    except Exception:
        pass

    return {"session": saved.model_dump()}


@router.get("/requirements/{req_id}/session")
async def get_session_state(workspace: str, req_id: str):
    store = _get_workspace(workspace)
    store.ensure_layout()
    try:
        store.requirements.get(req_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Requirement not found")

    existing = _find_existing_session(store, req_id)
    return {"session": existing.model_dump() if existing else None}


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

        # For change requests, accumulate context from all completed previous requirements
        baseline_context = None
        try:
            requirement = store.requirements.get(req_id)
            if requirement.kind == "change_request":
                all_reqs = store.requirements.list_all()
                sorted_reqs = sorted(all_reqs, key=lambda r: r.created_at)
                # Collect all requirements created before this one that have a completed session
                previous_contexts: list[dict[str, object]] = []
                for prev_req in sorted_reqs:
                    if prev_req.id == req_id:
                        break
                    prev_session = _find_existing_session(store, prev_req.id)
                    if prev_session and prev_session.meeting_context:
                        ctx = prev_session.meeting_context.model_dump()
                        previous_contexts.append({
                            "requirement_id": prev_req.id,
                            "title": prev_req.title,
                            "kind": prev_req.kind,
                            "status": prev_req.status,
                            "summary": ctx.get("summary", ""),
                            "goals": ctx.get("goals", []),
                            "acceptance_criteria": ctx.get("acceptance_criteria", []),
                        })
                if previous_contexts:
                    baseline_context = {
                        "product_evolution": previous_contexts,
                        "completed_count": len([c for c in previous_contexts if c["status"] == "done"]),
                    }
        except Exception:
            pass

        agent_context: dict[str, object] = {
            "requirement_id": req_id,
            "conversation": history,
            "current_context": session.meeting_context.model_dump() if session.meeting_context else {},
        }
        if baseline_context:
            agent_context["baseline_context"] = baseline_context

        payload = await run_in_threadpool(
            adapter.generate,
            "requirement_clarifier",
            agent_context,
        )
    except Exception as exc:
        session = session.model_copy(update={"status": "failed", "updated_at": datetime.now(UTC).isoformat()})
        store.clarifications.save(session)
        raise HTTPException(status_code=502, detail=f"Clarification agent failed: {exc}")

    reply_text = str(payload.reply)
    assistant_msg = ClarificationMessage(role="assistant", content=reply_text)
    session.messages.append(assistant_msg)

    raw = payload.meeting_context if isinstance(payload.meeting_context, dict) else {}
    validated_attendees = [a for a in raw.get("validated_attendees", []) if a in _SUPPORTED_ATTENDEES]
    if not validated_attendees:
        validated_attendees = _infer_validated_attendees(
            request.message.strip(),
            reply_text,
            *(message.content for message in session.messages[-4:]),
        )
    draft = MeetingContextDraft(
        summary=str(raw.get("summary", getattr(session.meeting_context, "summary", "pending") if session.meeting_context else "pending")),
        goals=[str(g) for g in raw.get("goals", [])],
        constraints=[str(c) for c in raw.get("constraints", [])],
        open_questions=[str(q) for q in raw.get("open_questions", [])],
        acceptance_criteria=[str(a) for a in raw.get("acceptance_criteria", [])],
        risks=[str(r) for r in raw.get("risks", [])],
        references=[str(ref) for ref in raw.get("references", [])],
        validated_attendees=validated_attendees,
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

    # If kickoff already in progress, return existing task instead of creating a duplicate
    if session.status == "kickoff_started" and session.kickoff_task_id:
        ws_root = resolve_workspace_root(workspace)
        service = KickoffService(ws_root, project_root=resolve_project_root(workspace))
        try:
            existing_task = service.get_task(session.kickoff_task_id)
            if existing_task.status in ("pending", "running"):
                return {
                    "task_id": existing_task.id,
                    "project_id": existing_task.project_id,
                    "status": "kickoff_started",
                }
            # Task is failed/completed — reset session and allow retry
            session = session.model_copy(update={
                "status": "failed",
                "updated_at": datetime.now(UTC).isoformat(),
            })
            store.clarifications.save(session)
        except FileNotFoundError:
            pass  # Task file missing, allow retry

    if not session.meeting_context or not session.readiness or not session.readiness.ready:
        missing = session.readiness.missing_fields if session.readiness else ["unknown"]
        raise HTTPException(status_code=400, detail=f"Session not ready for kickoff. Missing: {', '.join(missing)}")

    for attendee in session.meeting_context.validated_attendees:
        if attendee not in _SUPPORTED_ATTENDEES:
            raise HTTPException(status_code=400, detail=f"Unsupported attendee: {attendee}")

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

    session = session.model_copy(update={
        "kickoff_task_id": task.id,
        "updated_at": datetime.now(UTC).isoformat(),
    })
    store.clarifications.save(session)

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
