from pathlib import Path

from studio.runtime.graph import build_demo_runtime, build_design_graph
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def test_demo_runtime_runs_to_completion(tmp_path: Path) -> None:
    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert result["plan"]["current_node"] == "reviewer"
    assert result["artifacts"][0]["artifact_type"] == "design_brief"
    assert result["telemetry"]["status"] == "completed"
    assert result["telemetry"]["node_traces"]["planner"]["node"] == "planner"
    assert result["telemetry"]["node_traces"]["worker"]["llm_provider"] == "claude"
    assert "fallback_used" in result["telemetry"]["node_traces"]["worker"]
    assert result["telemetry"]["node_traces"]["reviewer"]["node"] == "reviewer"


def test_demo_runtime_surfaces_retry_when_review_fails(tmp_path: Path) -> None:
    runtime = build_demo_runtime(tmp_path, force_review_retry=True)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert "review retry requested" in result["risks"]
    assert result["telemetry"]["status"] == "needs_attention"


def test_design_graph_updates_requirement_and_design_doc(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Add relic system"))

    runtime = build_design_graph()
    result = runtime.invoke({"workspace_root": str(workspace_root), "requirement_id": "req_001"})

    updated_requirement = workspace.requirements.get("req_001")
    design_doc = workspace.design_docs.get(result["design_doc_id"])

    assert result["requirement_id"] == "req_001"
    assert result["node_name"] == "design"
    assert "design_doc_id" in result
    assert updated_requirement.status == "pending_user_review"
    assert updated_requirement.design_doc_id == result["design_doc_id"]
    assert design_doc.requirement_id == "req_001"
    assert design_doc.status == "pending_user_review"
