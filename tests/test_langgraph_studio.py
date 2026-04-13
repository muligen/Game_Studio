from importlib import import_module


def test_langgraph_studio_adapter_exposes_runnable_graph() -> None:
    module = import_module("studio.langgraph_app")
    assert hasattr(module, "graph")

    result = module.graph.invoke({"prompt": "Design a simple 2D game concept"})

    assert result["plan"]["current_node"] == "reviewer"
    assert result["telemetry"]["status"] == "completed"
