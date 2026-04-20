from importlib import import_module
from pathlib import Path

import pytest

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _disable_live_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "studio.llm.claude_worker.ClaudeWorkerAdapter.load_config",
        lambda self: type(
            "Config",
            (),
            {
                "enabled": False,
                "mode": "text",
                "model": None,
                "api_key": None,
                "base_url": None,
            },
        )(),
    )
    monkeypatch.setattr(
        "studio.llm.claude_roles.ClaudeRoleAdapter.load_config",
        lambda self: type(
            "Config",
            (),
            {
                "enabled": False,
                "mode": "text",
                "model": None,
                "api_key": None,
                "base_url": None,
            },
        )(),
    )


def test_langgraph_studio_adapter_exposes_workflow_graphs(tmp_path: Path) -> None:
    module = import_module("studio.langgraph_app")
    assert hasattr(module, "design_graph")
    assert hasattr(module, "delivery_graph")

    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Add relic system"))

    design_result = module.design_graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
        }
    )
    default_result = module.graph.invoke({"prompt": "Design a simple 2D game concept"})
    helper_result = module.build_langgraph_dev_runtime().invoke(
        {"prompt": "Design a simple 2D game concept"}
    )

    assert design_result["requirement_id"] == "req_001"
    assert design_result["node_name"] == "design"

    # Delivery graph expects requirement in "approved" status
    approved = workspace.requirements.get("req_001").model_copy(update={"status": "approved"})
    workspace.requirements.save(approved)

    delivery_result = module.delivery_graph.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
        }
    )
    assert delivery_result["node_name"] == "quality"
    assert default_result["plan"]["current_node"] == "reviewer"
    assert default_result["telemetry"]["status"] == "completed"
    assert helper_result["plan"]["current_node"] == "reviewer"
    assert helper_result["telemetry"]["status"] == "completed"


def test_langgraph_studio_default_graph_can_be_invoked_twice() -> None:
    module = import_module("studio.langgraph_app")

    first_result = module.graph.invoke({"prompt": "Design a simple 2D game concept"})
    second_result = module.graph.invoke({"prompt": "Design a simple 2D game concept"})

    assert first_result["run_id"] != second_result["run_id"]
    assert first_result["task_id"] != second_result["task_id"]
    assert first_result["artifacts"][0]["artifact_id"] != second_result["artifacts"][0]["artifact_id"]
    assert first_result["plan"]["current_node"] == "reviewer"
    assert second_result["plan"]["current_node"] == "reviewer"
    assert first_result["telemetry"]["status"] == "completed"
    assert second_result["telemetry"]["status"] == "completed"
