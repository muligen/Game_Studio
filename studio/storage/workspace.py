from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from studio.schemas.action_log import ActionLog
from studio.schemas.clarification import RequirementClarificationSession
from studio.schemas.balance_table import BalanceTable
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.delivery import (
    AgentSessionLease,
    DeliveryPlan,
    DeliveryTask,
    KickoffDecisionGate,
    TaskExecutionResult,
)
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.meeting_transcript import MeetingTranscript, MeetingTranscriptEvent
from studio.schemas.requirement import RequirementCard
from studio.schemas.session import ProjectAgentSession
from studio.storage.base import JsonRepository


class LogRepository(JsonRepository[ActionLog]):
    def new(
        self,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        message: str,
        metadata: dict[str, object],
    ) -> ActionLog:
        timestamp = datetime.now(UTC).isoformat()
        return ActionLog(
            id=f"log_{uuid4().hex}",
            timestamp=timestamp,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            message=message,
            metadata=metadata,
        )


class StudioWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.requirements = JsonRepository(root / "requirements", RequirementCard)
        self.design_docs = JsonRepository(root / "design_docs", DesignDoc)
        self.balance_tables = JsonRepository(root / "balance_tables", BalanceTable)
        self.bugs = JsonRepository(root / "bugs", BugCard)
        self.logs = LogRepository(root / "logs", ActionLog)
        self.meetings = JsonRepository(root / "meetings", MeetingMinutes)
        self.meeting_transcripts = JsonRepository(root / "meeting_transcripts", MeetingTranscript)
        self.sessions = JsonRepository(root / "project_agent_sessions", ProjectAgentSession)
        self.delivery_plans = JsonRepository(root / "delivery_plans", DeliveryPlan)
        self.delivery_tasks = JsonRepository(root / "delivery_tasks", DeliveryTask)
        self.decision_gates = JsonRepository(root / "kickoff_decision_gates", KickoffDecisionGate)
        self.execution_results = JsonRepository(root / "task_execution_results", TaskExecutionResult)
        self.session_leases = JsonRepository(root / "agent_session_leases", AgentSessionLease)
        self.clarifications = JsonRepository(root / "requirement_clarifications", RequirementClarificationSession)

    def ensure_layout(self) -> None:
        for repo_root in (
            self.requirements.root,
            self.design_docs.root,
            self.balance_tables.root,
            self.bugs.root,
            self.logs.root,
            self.meetings.root,
            self.meeting_transcripts.root,
            self.sessions.root,
            self.delivery_plans.root,
            self.delivery_tasks.root,
            self.decision_gates.root,
            self.execution_results.root,
            self.session_leases.root,
            self.clarifications.root,
            self.delivery_plans.root,
            self.delivery_tasks.root,
            self.decision_gates.root,
            self.execution_results.root,
            self.session_leases.root,
        ):
            repo_root.mkdir(parents=True, exist_ok=True)

    def append_meeting_transcript_event(
        self,
        *,
        meeting_id: str,
        requirement_id: str,
        project_id: str | None = None,
        agent_role: str,
        node_name: str,
        prompt: object,
        context: object,
        reply: object,
    ) -> MeetingTranscript:
        try:
            transcript = self.meeting_transcripts.get(meeting_id)
        except FileNotFoundError:
            transcript = MeetingTranscript(
                id=meeting_id,
                meeting_id=meeting_id,
                requirement_id=requirement_id,
                project_id=project_id,
            )

        event = MeetingTranscriptEvent(
            sequence=len(transcript.events) + 1,
            agent_role=agent_role,
            node_name=node_name,
            kind="llm",
            message=_summarize_transcript_reply(reply),
            prompt=str(prompt) if isinstance(prompt, str) else None,
            context=_transcript_dict(context),
            reply=_transcript_value(reply),
        )
        update: dict[str, object] = {"events": [*transcript.events, event]}
        if project_id:
            update["project_id"] = project_id
        updated = transcript.model_copy(update=update)
        self.meeting_transcripts.save(updated)
        return updated

    def save_meeting_transcript(
        self,
        *,
        meeting_id: str,
        requirement_id: str,
        project_id: str | None = None,
        events: list[dict[str, object]],
    ) -> MeetingTranscript:
        transcript = MeetingTranscript(
            id=meeting_id,
            meeting_id=meeting_id,
            requirement_id=requirement_id,
            project_id=project_id,
            events=[
                MeetingTranscriptEvent(
                    sequence=index,
                    agent_role=str(event["agent_role"]),
                    node_name=str(event["node_name"]),
                    kind="llm",
                    message=str(event["message"]),
                    prompt=str(event["prompt"]) if isinstance(event.get("prompt"), str) else None,
                    context=_transcript_dict(event.get("context")),
                    reply=_transcript_value(event.get("reply")),
                )
                for index, event in enumerate(events, start=1)
            ],
        )
        self.meeting_transcripts.save(transcript)
        return transcript


def _transcript_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _transcript_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_transcript_value(item) for item in value]
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _transcript_value(value.model_dump())
    if hasattr(value, "__dict__"):
        return _transcript_value(vars(value))
    return str(value)


def _transcript_dict(value: object) -> dict[str, object]:
    normalized = _transcript_value(value)
    if isinstance(normalized, dict):
        return normalized
    return {}


def _summarize_transcript_reply(reply: object) -> str:
    normalized = _transcript_value(reply)
    if isinstance(normalized, str) and normalized.strip():
        return normalized.strip()
    if isinstance(normalized, dict):
        for key in ("summary", "title", "reason", "reply"):
            value = normalized.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Structured transcript event"
