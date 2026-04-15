from __future__ import annotations

import logging
from pathlib import Path

from studio.runtime.graph import build_design_graph
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace

logger = logging.getLogger(__name__)


class DesignWorkflowExecutor:
    """Execute the design workflow for a single requirement.

    Wraps the LangGraph design graph, invoking it with the correct
    input state and returning the result dict.
    """

    def run(
        self,
        workspace: StudioWorkspace,
        requirement: RequirementCard,
        *,
        workspace_root: str,
    ) -> dict[str, object]:
        graph = build_design_graph()
        graph_input: dict[str, object] = {
            "workspace_root": workspace_root,
            "requirement_id": requirement.id,
        }
        result = graph.invoke(graph_input)
        logger.info(
            "design workflow completed for %s: design_doc_id=%s",
            requirement.id,
            result.get("design_doc_id"),
        )
        return result
