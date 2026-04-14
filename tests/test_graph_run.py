from pathlib import Path

from studio.runtime.graph import build_demo_runtime


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
