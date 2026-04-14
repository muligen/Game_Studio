from importlib import import_module
from pathlib import Path

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def test_langgraph_studio_adapter_exposes_workflow_graphs(tmp_path: Path) -> None:
    module = import_module("studio.langgraph_app")
    assert hasattr(module, "design_graph")
    assert hasattr(module, "delivery_graph")

    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Add relic system"))

    design_result = module.design_graph.invoke(
        {"workspace_root": str(workspace_root), "requirement_id": "req_001"}
    )
    default_result = module.graph.invoke({"prompt": "Design a simple 2D game concept"})
    helper_result = module.build_langgraph_dev_runtime().invoke(
        {"prompt": "Design a simple 2D game concept"}
    )

    assert design_result["requirement_id"] == "req_001"
    assert design_result["node_name"] == "design"
    delivery_result = module.delivery_graph.invoke(
        {"workspace_root": str(workspace_root), "requirement_id": "req_001"}
    )
    assert delivery_result["node_name"] == "quality"
    assert default_result["plan"]["current_node"] == "reviewer"
    assert default_result["telemetry"]["status"] == "completed"
    assert helper_result["plan"]["current_node"] == "reviewer"
    assert helper_result["telemetry"]["status"] == "completed"
