from __future__ import annotations

from pathlib import Path

from studio.runtime.graph import build_demo_runtime, build_delivery_graph, build_design_graph, build_meeting_graph

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANGGRAPH_WORKSPACE = _REPO_ROOT / ".runtime-data" / "langgraph-dev"


def build_langgraph_dev_runtime():
    """Backward-compatible alias for the existing demo runtime entrypoint."""
    return build_demo_runtime(DEFAULT_LANGGRAPH_WORKSPACE)


design_graph = build_design_graph()
delivery_graph = build_delivery_graph()
meeting_graph = build_meeting_graph()
graph = build_langgraph_dev_runtime()
