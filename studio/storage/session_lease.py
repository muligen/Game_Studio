from __future__ import annotations

from pathlib import Path

from studio.schemas.delivery import AgentSessionLease
from studio.storage.base import JsonRepository


class SessionLeaseManager:
    def __init__(self, root: Path) -> None:
        self._repo = JsonRepository(root / "agent_session_leases", AgentSessionLease)

    def acquire(self, project_id: str, agent: str, task_id: str, session_id: str) -> AgentSessionLease:
        existing = self.find(project_id, agent)
        if existing is not None and existing.status == "held":
            raise ValueError(f"session lease already held by task {existing.task_id}")
        lease = AgentSessionLease(
            project_id=project_id,
            agent=agent,
            task_id=task_id,
            session_id=session_id,
        )
        return self._repo.save(lease)

    def release(self, project_id: str, agent: str) -> AgentSessionLease:
        composite_id = f"{project_id}_{agent}"
        try:
            lease = self._repo.get(composite_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"no lease for {composite_id}") from exc
        updated = lease.model_copy(update={"status": "released"})
        return self._repo.save(updated)

    def find(self, project_id: str, agent: str) -> AgentSessionLease | None:
        composite_id = f"{project_id}_{agent}"
        try:
            return self._repo.get(composite_id)
        except (FileNotFoundError, ValueError):
            return None

    def is_available(self, project_id: str, agent: str) -> bool:
        lease = self.find(project_id, agent)
        return lease is None or lease.status != "held"
