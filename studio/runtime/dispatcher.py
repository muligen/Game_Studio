from __future__ import annotations

from studio.agents.art import ArtAgent
from studio.agents.design import DesignAgent
from studio.agents.dev import DevAgent
from studio.agents.qa import QaAgent
from studio.agents.quality import QualityAgent
from studio.agents.planner import PlannerAgent
from studio.agents.reviewer import ReviewerAgent
from studio.agents.worker import WorkerAgent


class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agents = {
            "design": DesignAgent(),
            "dev": DevAgent(),
            "qa": QaAgent(),
            "quality": QualityAgent(),
            "art": ArtAgent(),
            "planner": PlannerAgent(),
            "worker": WorkerAgent(),
            "reviewer": ReviewerAgent(),
        }

    def get(self, node_name: str):
        return self._agents[node_name]
