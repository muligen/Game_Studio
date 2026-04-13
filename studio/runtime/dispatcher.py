from __future__ import annotations

from studio.agents.planner import PlannerAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent


class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agents = {
            "planner": PlannerAgent(),
            "worker": WorkerAgent(),
            "reviewer": ReviewerAgent(),
        }

    def get(self, node_name: str):
        return self._agents[node_name]
