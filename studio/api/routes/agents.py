from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

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
        response_text = await run_in_threadpool(_run_chat, ws_root, session.session_id, agent, request.message)
    except ClaudeRoleError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    SessionRegistry(ws_root).touch(project_id, agent)

    return {"role": "assistant", "content": response_text}


def _run_chat(ws_root, session_id: str, agent: str, message: str) -> str:
    from studio.llm.claude_roles import ClaudeRoleAdapter

    profile = AgentProfileLoader().load(agent)
    adapter = ClaudeRoleAdapter(
        project_root=resolve_project_root(str(ws_root).replace(".studio-data", "").rstrip("/")),
        profile=profile,
        session_id=session_id,
        resume_session=True,
    )
    return adapter.chat(message)
