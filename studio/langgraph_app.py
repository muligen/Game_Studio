from __future__ import annotations

from pathlib import Path

from studio.runtime.graph import build_demo_runtime

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANGGRAPH_WORKSPACE = _REPO_ROOT / ".runtime-data" / "langgraph-dev"


def build_langgraph_dev_runtime():
    """Expose the existing demo runtime through a stable LangGraph entrypoint."""
    return build_demo_runtime(DEFAULT_LANGGRAPH_WORKSPACE)


graph = build_langgraph_dev_runtime()
