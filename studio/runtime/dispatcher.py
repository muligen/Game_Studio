from __future__ import annotations

from importlib import import_module
from typing import Any


class RuntimeDispatcher:
    def __init__(self) -> None:
        self._agent_specs = {
            "design": "studio.agents.design:DesignAgent",
            "dev": "studio.agents.dev:DevAgent",
            "qa": "studio.agents.qa:QaAgent",
            "quality": "studio.agents.quality:QualityAgent",
            "art": "studio.agents.art:ArtAgent",
            "planner": "studio.agents.planner:PlannerAgent",
            "worker": "studio.agents.worker:WorkerAgent",
            "reviewer": "studio.agents.reviewer:ReviewerAgent",
        }
        self._agents: dict[str, Any] = {}

    def get(self, node_name: str):
        agent = self._agents.get(node_name)
        if agent is None:
            module_path, class_name = self._agent_specs[node_name].split(":")
            module = import_module(module_path)
            agent = getattr(module, class_name)()
            self._agents[node_name] = agent
        return agent
