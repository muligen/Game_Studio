import json
from pathlib import Path

import pytest

from studio.runtime.graph import build_demo_runtime, build_design_graph
from studio.schemas.artifact import ArtifactRecord
from studio.schemas.requirement import RequirementCard
from studio.schemas.runtime import NodeDecision, NodeResult
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


def test_demo_runtime_persists_unique_memory_and_checkpoint_keys_per_run(tmp_path: Path) -> None:
    first_runtime = build_demo_runtime(tmp_path)
    second_runtime = build_demo_runtime(tmp_path)

    first_result = first_runtime.invoke({"prompt": "Design a simple 2D game concept"})
    second_result = second_runtime.invoke({"prompt": "Design a simple 2D game concept"})

    memory_entries = sorted((tmp_path / "memory" / "run").glob("*.json"))
    checkpoint_entries = sorted((tmp_path / "checkpoints").glob("*.json"))

    assert first_result["run_id"] != second_result["run_id"]
    assert len(memory_entries) == 2
    assert len({entry.stem for entry in memory_entries}) == 2
    assert len(checkpoint_entries) == 6
    assert len({entry.stem for entry in checkpoint_entries}) == 6


def test_demo_runtime_preserves_state_patch_fields_in_result_and_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StubAgent:
        def __init__(self, result: NodeResult) -> None:
            self._result = result

        def run(self, state, **kwargs):
            return self._result

    class _StubDispatcher:
        def __init__(self) -> None:
            self._agents = {
                "planner": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={
                            "plan": {"current_node": "planner"},
                            "memory_refs": ["planner-ref"],
                        },
                        trace={"node": "planner"},
                    )
                ),
                "worker": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={
                            "plan": {"current_node": "worker"},
                            "human_gates": [{"gate_id": "gate-1", "reason": "inspect"}],
                        },
                        artifacts=[
                            ArtifactRecord(
                                artifact_id="concept-draft",
                                artifact_type="design_brief",
                                source_node="worker",
                                payload={"title": "Relics", "summary": "desc", "genre": "rpg"},
                            )
                        ],
                        trace={"node": "worker"},
                    )
                ),
                "reviewer": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={
                            "plan": {"current_node": "reviewer"},
                            "risks": ["reviewed"],
                        },
                        trace={"node": "reviewer"},
                    )
                ),
            }

        def get(self, node_name: str):
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _StubDispatcher)

    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    checkpoint_payloads = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "checkpoints").glob("*.json")
    }

    assert result["memory_refs"] == ["planner-ref"]
    assert result["human_gates"] == [{"gate_id": "gate-1", "reason": "inspect", "status": "pending"}]
    assert result["risks"] == ["reviewed"]
    assert any(payload["memory_refs"] == ["planner-ref"] for payload in checkpoint_payloads.values())
    assert any(payload["human_gates"] == [{"gate_id": "gate-1", "reason": "inspect", "status": "pending"}] for payload in checkpoint_payloads.values())
    assert any(payload["risks"] == ["reviewed"] for payload in checkpoint_payloads.values())


def test_demo_runtime_stays_completed_when_reviewer_continues_with_risks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StubAgent:
        def __init__(self, result: NodeResult) -> None:
            self._result = result

        def run(self, state, **kwargs):
            return self._result

    class _StubDispatcher:
        def __init__(self) -> None:
            self._agents = {
                "planner": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={"plan": {"current_node": "planner"}},
                        trace={"node": "planner"},
                    )
                ),
                "worker": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={"plan": {"current_node": "worker"}},
                        artifacts=[
                            ArtifactRecord(
                                artifact_id="concept-draft",
                                artifact_type="design_brief",
                                source_node="worker",
                                payload={"title": "Relics", "summary": "desc", "genre": "rpg"},
                            )
                        ],
                        trace={"node": "worker"},
                    )
                ),
                "reviewer": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={
                            "plan": {"current_node": "reviewer"},
                            "risks": ["watch economy balance"],
                        },
                        trace={"node": "reviewer"},
                    )
                ),
            }

        def get(self, node_name: str):
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _StubDispatcher)

    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert result["risks"] == ["watch economy balance"]
    assert result["telemetry"]["status"] == "completed"


def test_demo_runtime_handles_missing_review_artifact_without_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StubAgent:
        def __init__(self, result: NodeResult) -> None:
            self._result = result

        def run(self, state, **kwargs):
            return self._result

    class _StubDispatcher:
        def __init__(self) -> None:
            self._agents = {
                "planner": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={"plan": {"current_node": "planner"}},
                        trace={"node": "planner"},
                    )
                ),
                "worker": _StubAgent(
                    NodeResult(
                        decision=NodeDecision.CONTINUE,
                        state_patch={"plan": {"current_node": "worker"}},
                        artifacts=[],
                        trace={"node": "worker"},
                    )
                ),
            }

        def get(self, node_name: str):
            if node_name == "reviewer":
                raise AssertionError("reviewer should not run when there are no artifacts")
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _StubDispatcher)

    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert "missing review artifact" in result["risks"]
    assert result["telemetry"]["status"] == "needs_attention"
    assert result["telemetry"]["node_traces"]["reviewer"]["reason"] == "missing_artifact"


def test_demo_runtime_writes_llm_io_logs_without_exposing_prompt_in_telemetry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StubWorkerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "worker"}},
                artifacts=[
                    ArtifactRecord(
                        artifact_id="concept-draft",
                        artifact_type="design_brief",
                        source_node="worker",
                        payload={"title": "Relics", "summary": "desc", "genre": "rpg"},
                    )
                ],
                trace={"node": "worker", "llm_provider": "claude", "fallback_used": False},
            )

        def consume_llm_log_entry(self):
            return {
                "prompt": "worker prompt",
                "context": {"prompt": "Design a simple 2D game concept"},
                "reply": {"title": "Relics", "summary": "desc", "genre": "rpg"},
            }

    class _StubReviewerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "reviewer"}, "risks": []},
                trace={"node": "reviewer", "llm_provider": "claude", "fallback_used": False},
            )

        def consume_llm_log_entry(self):
            return {
                "prompt": "reviewer prompt",
                "context": {"artifact_payload": {"title": "Relics", "summary": "desc", "genre": "rpg"}},
                "reply": {"decision": "continue", "reason": "ok", "risks": []},
            }

    class _StubPlannerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "planner"}},
                trace={"node": "planner"},
            )

    class _StubDispatcher:
        def __init__(self) -> None:
            self._agents = {
                "planner": _StubPlannerAgent(),
                "worker": _StubWorkerAgent(),
                "reviewer": _StubReviewerAgent(),
            }

        def get(self, node_name: str):
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _StubDispatcher)

    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    assert "llm_prompt" not in result["telemetry"]["node_traces"]["worker"]
    assert "llm_context" not in result["telemetry"]["node_traces"]["reviewer"]

    log_entries = json.loads(
        (tmp_path / "logs" / f'{result["run_id"]}.json').read_text(encoding="utf-8")
    )
    assert [entry["node_name"] for entry in log_entries] == ["worker", "reviewer"]
    assert log_entries[0]["prompt"] == "worker prompt"
    assert log_entries[0]["reply"]["title"] == "Relics"
    assert log_entries[1]["prompt"] == "reviewer prompt"
    assert log_entries[1]["reply"]["decision"] == "continue"


def test_demo_runtime_llm_logs_serialize_structured_reply_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StructuredReply:
        def model_dump(self) -> dict[str, object]:
            return {"decision": "continue", "reason": "ok", "risks": []}

    class _StubWorkerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "worker"}},
                artifacts=[
                    ArtifactRecord(
                        artifact_id="concept-draft",
                        artifact_type="design_brief",
                        source_node="worker",
                        payload={"title": "Relics", "summary": "desc", "genre": "rpg"},
                    )
                ],
                trace={"node": "worker", "llm_provider": "claude", "fallback_used": False},
            )

        def consume_llm_log_entry(self):
            return {
                "prompt": "worker prompt",
                "context": {"prompt": "Design a simple 2D game concept"},
                "reply": {"title": "Relics", "summary": "desc", "genre": "rpg"},
            }

    class _StubReviewerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "reviewer"}, "risks": []},
                trace={"node": "reviewer", "llm_provider": "claude", "fallback_used": False},
            )

        def consume_llm_log_entry(self):
            return {
                "prompt": "reviewer prompt",
                "context": {"artifact_payload": {"title": "Relics", "summary": "desc", "genre": "rpg"}},
                "reply": _StructuredReply(),
            }

    class _StubPlannerAgent:
        def run(self, state, **kwargs):
            return NodeResult(
                decision=NodeDecision.CONTINUE,
                state_patch={"plan": {"current_node": "planner"}},
                trace={"node": "planner"},
            )

    class _StubDispatcher:
        def __init__(self) -> None:
            self._agents = {
                "planner": _StubPlannerAgent(),
                "worker": _StubWorkerAgent(),
                "reviewer": _StubReviewerAgent(),
            }

        def get(self, node_name: str):
            return self._agents[node_name]

    monkeypatch.setattr("studio.runtime.graph.RuntimeDispatcher", _StubDispatcher)

    runtime = build_demo_runtime(tmp_path)
    result = runtime.invoke({"prompt": "Design a simple 2D game concept"})

    log_entries = json.loads(
        (tmp_path / "logs" / f'{result["run_id"]}.json').read_text(encoding="utf-8")
    )
    assert log_entries[1]["reply"] == {"decision": "continue", "reason": "ok", "risks": []}


def test_design_graph_updates_requirement_and_design_doc(tmp_path: Path) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Add relic system"))

    runtime = build_design_graph()
    result = runtime.invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
        }
    )

    updated_requirement = workspace.requirements.get("req_001")
    design_doc = workspace.design_docs.get(result["design_doc_id"])

    assert result["requirement_id"] == "req_001"
    assert result["node_name"] == "design"
    assert "design_doc_id" in result
    assert updated_requirement.status == "pending_user_review"
    assert updated_requirement.design_doc_id == result["design_doc_id"]
    assert design_doc.requirement_id == "req_001"
    assert design_doc.id == updated_requirement.design_doc_id
    # With DesignAgent fallback, we get default values when Claude is disabled
    assert design_doc.title == "Design Brief Draft"
    assert design_doc.summary == "Add relic system"
    assert design_doc.status == "pending_user_review"
    # Fallback produces empty lists
    assert design_doc.core_rules == []
    assert design_doc.acceptance_criteria == []
    assert design_doc.open_questions == []


def test_design_graph_rejects_missing_required_inputs(tmp_path: Path) -> None:
    runtime = build_design_graph()

    with pytest.raises(ValueError, match="workspace_root is required"):
        runtime.invoke({"requirement_id": "req_001"})

    with pytest.raises(ValueError, match="project_root is required"):
        runtime.invoke({"workspace_root": str(tmp_path / ".studio-data"), "requirement_id": "req_001"})

    with pytest.raises(ValueError, match="requirement_id is required"):
        runtime.invoke({"workspace_root": str(tmp_path / ".studio-data"), "project_root": str(tmp_path)})


def test_design_graph_uses_design_agent():
    """design_node should call DesignAgent and use its output for the design doc."""
    from unittest.mock import patch, MagicMock

    with (
        patch("studio.agents.design.DesignAgent") as MockAgent,
        patch("studio.runtime.graph.StudioWorkspace") as MockWorkspace,
    ):
        mock_agent = MagicMock()
        mock_agent.run.return_value = NodeResult(
            decision=NodeDecision.CONTINUE,
            state_patch={
                "plan": {"current_node": "design"},
                "telemetry": {
                    "design_brief": {
                        "title": "Moonwell Garden",
                        "summary": "A relaxing garden game",
                        "core_rules": ["water plants daily"],
                        "acceptance_criteria": ["plants grow over time"],
                        "open_questions": ["weather system?"],
                    }
                },
            },
            trace={"node": "design", "fallback_used": False},
        )
        MockAgent.return_value = mock_agent

        mock_req = RequirementCard(id="req_1", title="Garden Game")
        mock_designs = MagicMock()
        mock_requirements = MagicMock()
        mock_requirements.get.return_value = mock_req

        mock_store = MagicMock()
        mock_store.requirements = mock_requirements
        mock_store.design_docs = mock_designs
        MockWorkspace.return_value = mock_store

        graph = build_design_graph()
        result = graph.invoke({
            "workspace_root": "/tmp/test-workspace",
            "project_root": "/tmp",
            "requirement_id": "req_1",
        })

        mock_agent.run.assert_called_once()
        saved_doc = mock_designs.save.call_args[0][0]
        assert saved_doc.core_rules == ["water plants daily"]
        assert saved_doc.acceptance_criteria == ["plants grow over time"]
        assert saved_doc.open_questions == ["weather system?"]
