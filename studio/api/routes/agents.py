from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from claude_agent_sdk import get_session_messages as sdk_get_session_messages

from studio.agents.profile_loader import AgentProfileLoader
from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root
from studio.llm import ClaudeRoleError
from studio.storage.session_lease import SessionLeaseManager
from studio.storage.session_registry import SessionRegistry
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


@router.post("/{project_id}/{agent}/chat")
async def chat_with_agent(
    project_id: str,
    agent: str,
    request: ChatRequest,
    workspace: str,
) -> dict:
    """Send a message to an idle agent and get a response."""
    ws_root = resolve_workspace_root(workspace)

    session = SessionRegistry(ws_root).find(project_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    lease_mgr = SessionLeaseManager(ws_root)
    if not lease_mgr.is_available(project_id, agent):
        raise HTTPException(status_code=409, detail="Agent is busy")

    try:
        response_text = await run_in_threadpool(
            _run_chat,
            ws_root,
            session.session_id,
            agent,
            request.message,
            session.project_dir,
        )
    except ClaudeRoleError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    SessionRegistry(ws_root).touch(project_id, agent)

    return {"role": "assistant", "content": response_text}


@router.get("/{project_id}/{agent}/messages")
async def get_agent_messages(
    project_id: str,
    agent: str,
    workspace: str,
) -> dict:
    """Load chat history for an agent session from the Claude CLI transcript."""
    ws_root = resolve_workspace_root(workspace)

    session = SessionRegistry(ws_root).find(project_id, agent)
    if session is None:
        return {"messages": []}

    transcript_dir = session.project_dir or session.agent_config_dir
    if transcript_dir is None:
        profile = AgentProfileLoader().load(agent)
        project_root = resolve_project_root(str(ws_root).replace(".studio-data", "").rstrip("/"))
        claude_root = profile.claude_project_root
        transcript_dir = str(claude_root if claude_root.is_absolute() else (project_root / claude_root).resolve())

    try:
        sdk_messages = sdk_get_session_messages(
            session.session_id,
            directory=str(transcript_dir),
        )
    except Exception:
        logger.exception("Failed to load messages for session %s", session.session_id)
        return {"messages": []}

    messages: list[dict] = []
    for msg in sdk_messages:
        content = _extract_content_text(msg.message)
        if not content:
            continue
        messages.append({
            "role": msg.type,
            "content": content,
            "uuid": msg.uuid,
        })

    return {"messages": messages}


def _extract_content_text(message: dict) -> str:
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def _run_chat(ws_root, session_id: str, agent: str, message: str, project_dir: str | None = None) -> str:
    from studio.llm.claude_roles import ClaudeRoleAdapter

    profile = AgentProfileLoader().load(agent)
    adapter = ClaudeRoleAdapter(
        project_root=resolve_project_root(str(ws_root).replace(".studio-data", "").rstrip("/")),
        profile=profile,
        session_id=session_id,
        resume_session=True,
        project_dir=None if project_dir is None else Path(project_dir),
    )
    return adapter.chat(message)
