from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from studio.schemas.action_log import ActionLog
from studio.schemas.balance_table import BalanceTable
from studio.schemas.bug import BugCard
from studio.schemas.design_doc import DesignDoc
from studio.schemas.meeting import MeetingMinutes
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
        self.sessions = JsonRepository(root / "project_agent_sessions", ProjectAgentSession)

    def ensure_layout(self) -> None:
        for repo_root in (
            self.requirements.root,
            self.design_docs.root,
            self.balance_tables.root,
            self.bugs.root,
            self.logs.root,
            self.meetings.root,
            self.sessions.root,
        ):
            repo_root.mkdir(parents=True, exist_ok=True)
