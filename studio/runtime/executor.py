from __future__ import annotations

import logging
from pathlib import Path

from studio.runtime.graph import build_delivery_graph, build_design_graph
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
        # The actual project root is two levels up from workspace data directory
        # workspace_root is like ".studio-data/.studio-data", project_root is the repo root
        project_root = str(Path(workspace_root).parent.parent)
        graph_input: dict[str, object] = {
            "workspace_root": workspace_root,
            "project_root": project_root,
            "requirement_id": requirement.id,
        }
        result = graph.invoke(graph_input)
        logger.info(
            "design workflow completed for %s: design_doc_id=%s",
            requirement.id,
            result.get("design_doc_id"),
        )
        return result


class DeliveryWorkflowExecutor:
    """Execute the delivery workflow (dev → qa → quality) for a single requirement.

    Wraps the LangGraph delivery graph, invoking it with the correct
    input state and returning the result dict.
    """

    def run(
        self,
        workspace: StudioWorkspace,
        requirement: RequirementCard,
        *,
        workspace_root: str,
    ) -> dict[str, object]:
        graph = build_delivery_graph()
        project_root = str(Path(workspace_root).parent.parent)
        graph_input: dict[str, object] = {
            "workspace_root": workspace_root,
            "project_root": project_root,
            "requirement_id": requirement.id,
        }
        result = graph.invoke(graph_input)
        logger.info(
            "delivery workflow completed for %s: quality_ready=%s",
            requirement.id,
            result.get("quality_ready"),
        )
        return result
