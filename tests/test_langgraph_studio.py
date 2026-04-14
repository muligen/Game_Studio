from importlib import import_module


def test_langgraph_studio_adapter_exposes_workflow_graphs() -> None:
    module = import_module("studio.langgraph_app")
    assert hasattr(module, "design_graph")
    assert hasattr(module, "delivery_graph")
    assert module.graph is module.design_graph

    design_result = module.design_graph.invoke(
        {"workspace_root": ".runtime-data/langgraph-dev", "requirement_id": "req_001"}
    )
    delivery_result = module.delivery_graph.invoke({"workspace_root": ".runtime-data/langgraph-dev"})

    assert design_result["requirement_id"] == "req_001"
    assert design_result["node_name"] == "design"
    assert delivery_result["node_name"] == "quality"
