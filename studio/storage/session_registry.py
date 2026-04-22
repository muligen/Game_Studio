from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from studio.schemas.session import ProjectAgentSession
from studio.storage.base import JsonRepository


class SessionRegistry:
    def __init__(self, root: Path) -> None:
        self._repo = JsonRepository(root / "project_agent_sessions", ProjectAgentSession)

    def create(self, project_id: str, requirement_id: str, agent: str, session_id: str) -> ProjectAgentSession:
        record = ProjectAgentSession(
            project_id=project_id,
            requirement_id=requirement_id,
            agent=agent,
            session_id=session_id,
        )
        return self._repo.save(record)

    def find(self, project_id: str, agent: str) -> ProjectAgentSession | None:
        composite_id = f"{project_id}_{agent}"
        try:
            return self._repo.get(composite_id)
        except (FileNotFoundError, ValueError):
            return None

    def touch(self, project_id: str, agent: str) -> ProjectAgentSession:
        composite_id = f"{project_id}_{agent}"
        try:
            record = self._repo.get(composite_id)
        except (FileNotFoundError, ValueError) as exc:
            raise FileNotFoundError("project agent session not found") from exc
        updated = record.model_copy(update={"last_used_at": datetime.now(UTC).isoformat()})
        return self._repo.save(updated)

    def create_all(self, project_id: str, requirement_id: str, agents: Sequence[str]) -> list[ProjectAgentSession]:
        sessions: list[ProjectAgentSession] = []
        for agent in agents:
            session_id = f"{project_id}_{agent}_{uuid.uuid4().hex[:12]}"
            sessions.append(self.create(project_id, requirement_id, agent, session_id))
        return sessions
