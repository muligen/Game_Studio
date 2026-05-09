from __future__ import annotations

from pathlib import Path

import pytest

from studio.llm import ClaudeRoleError
from studio.schemas.assumption import NeedsAttentionItem
from studio.schemas.design_doc import DesignDoc
from studio.schemas.delivery import DeliveryPlan, GateItem, KickoffDecisionGate
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.schemas.session import ProjectAgentSession
from studio.storage.delivery_plan_service import DeliveryPlanService
from studio.storage.workspace import StudioWorkspace


def _completed_meeting(tmp_path: Path, **overrides: object) -> MeetingMinutes:
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    defaults = {
        "id": "meet_001",
        "requirement_id": "req_001",
        "title": "Kickoff Meeting",
        "status": "completed",
        "decisions": ["Use turn-based combat"],
        "consensus_points": ["Scope agreed"],
        "pending_user_decisions": [],
    }
    defaults.update(overrides)
    meeting = MeetingMinutes(**defaults)
    ws.meetings.save(meeting)
    return meeting


def _requirement(tmp_path: Path) -> RequirementCard:
    ws = StudioWorkspace(tmp_path)
    req = RequirementCard(id="req_001", title="Turn-based battle MVP", status="approved")
    ws.requirements.save(req)
    return req


def _design_doc(tmp_path: Path) -> DesignDoc:
    ws = StudioWorkspace(tmp_path)
    doc = DesignDoc(
        id="design_001",
        requirement_id="req_001",
        title="Battle Loop Design",
        summary="Summarizes the intended turn loop.",
        core_rules=["Units act by speed order"],
        acceptance_criteria=["One full battle can finish"],
        open_questions=[],
        status="approved",
    )
    ws.design_docs.save(doc)
    return doc


def _create_session(
    tmp_path: Path,
    *,
    project_id: str = "proj_001",
    agent: str = "design",
    session_id: str = "sess_design_001",
) -> ProjectAgentSession:
    ws = StudioWorkspace(tmp_path)
    session = ProjectAgentSession(
        project_id=project_id,
        requirement_id="req_001",
        agent=agent,
        session_id=session_id,
    )
    ws.sessions.save(session)
    return session


def _planner_payload(
    *,
    tasks: list[dict[str, object]] | None = None,
    gate_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "tasks": tasks
        if tasks is not None
        else [
            {
                "title": "Design battle flow",
                "description": "Write the flow spec",
                "owner_agent": "design",
                "depends_on": [],
                "acceptance_criteria": ["Spec reviewed"],
            },
            {
                "title": "Implement battle flow",
                "description": "Build the core loop",
                "owner_agent": "dev",
                "depends_on": ["Design battle flow"],
                "acceptance_criteria": ["Tests pass"],
            },
        ],
        "decision_gate": {"items": gate_items or []},
    }


class FakePlanner:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or _planner_payload()
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate(self, context: dict[str, object]) -> dict[str, object]:
        self.calls.append(context)
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.fixture()
def planner() -> FakePlanner:
    return FakePlanner()


@pytest.fixture()
def svc(tmp_path: Path, planner: FakePlanner) -> DeliveryPlanService:
    return DeliveryPlanService(tmp_path, planner=planner)


class TestGeneratePlan:
    @staticmethod
    def test_invokes_planner_with_workspace_context(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Pick elemental scope"])
        _requirement(tmp_path)
        _design_doc(tmp_path)
        _create_session(tmp_path, project_id="proj_001", agent="design")

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "active"
        assert len(result["tasks"]) == 3  # 2 planner tasks + 1 auto-added documentation task
        assert planner.calls, "planner should have been invoked"
        context = planner.calls[0]
        assert context["meeting"]["id"] == "meet_001"
        assert context["requirement"]["id"] == "req_001"
        assert context["design_docs"][0]["id"] == "design_001"
        assert context["project_sessions"][0]["agent"] == "design"

    @staticmethod
    def test_rejects_incomplete_meeting(svc: DeliveryPlanService, tmp_path: Path) -> None:
        _completed_meeting(tmp_path, status="draft")
        _requirement(tmp_path)

        with pytest.raises(ValueError, match="not completed"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_falls_back_for_unknown_owner_agent(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            tasks=[
                {
                    "title": "Do stuff",
                    "description": "Things",
                    "owner_agent": "unknown_agent",
                    "depends_on": [],
                    "acceptance_criteria": [],
                },
            ],
        )

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["tasks"][0].owner_agent == "dev"

    @staticmethod
    def test_normalizes_known_owner_agent_aliases(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            tasks=[
                {
                    "title": "Design battle flow",
                    "description": "Write the flow spec",
                    "owner_agent": "design_agent",
                    "depends_on": [],
                    "acceptance_criteria": ["Spec reviewed"],
                },
                {
                    "title": "Implement battle flow",
                    "description": "Build the core loop",
                    "owner_agent": "dev_agent",
                    "depends_on": ["Design battle flow"],
                    "acceptance_criteria": ["Tests pass"],
                },
                {
                    "title": "Validate battle flow",
                    "description": "Test the core loop",
                    "owner_agent": "qa_agent",
                    "depends_on": ["Implement battle flow"],
                    "acceptance_criteria": ["Coverage reviewed"],
                },
            ],
        )

        result = svc.generate_plan("meet_001", "proj_001")

        assert [task.owner_agent for task in result["tasks"]] == ["design", "dev", "qa", "quality"]

    @staticmethod
    def test_rejects_cyclic_dependencies(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            tasks=[
                {
                    "title": "Task A",
                    "description": "A",
                    "owner_agent": "dev",
                    "depends_on": ["Task B"],
                    "acceptance_criteria": [],
                },
                {
                    "title": "Task B",
                    "description": "B",
                    "owner_agent": "dev",
                    "depends_on": ["Task A"],
                    "acceptance_criteria": [],
                },
            ],
        )

        with pytest.raises(ValueError, match="cycle"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_surfaces_planner_errors_without_fallback(tmp_path: Path) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        svc = DeliveryPlanService(tmp_path, planner=FakePlanner(error=ClaudeRoleError("claude_disabled")))

        with pytest.raises(ClaudeRoleError, match="claude_disabled"):
            svc.generate_plan("meet_001", "proj_001")

    @staticmethod
    def test_creates_preview_tasks_when_gate_exists(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path, pending_user_decisions=["Choose status effect scope"])
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "awaiting_user_decision"
        assert result["decision_gate"] is not None
        assert [task.status for task in result["tasks"]] == ["preview", "preview", "preview"]

    @staticmethod
    def test_ignores_decision_placeholder_dependency_when_gate_exists(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
        _requirement(tmp_path)
        planner.payload = {
            "tasks": [
                {
                    "title": "Implement snake visuals",
                    "description": "Apply the chosen visual direction.",
                    "owner_agent": "design",
                    "depends_on": ["STAKEHOLDER_DECISION_PAUSE"],
                    "acceptance_criteria": ["Visual direction is reflected in the board."],
                },
            ],
            "decision_gate": {
                "items": [
                    {
                        "id": "visual_direction",
                        "question": "Which visual direction should be used?",
                        "context": "Meeting raised visual ambiguity.",
                        "options": ["classic arcade", "minimal"],
                    },
                ],
            },
        }

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["tasks"][0].depends_on_task_ids == []
        assert result["tasks"][0].status == "preview"

    @staticmethod
    def test_ignores_decision_gate_dependency_when_gate_exists(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path, pending_user_decisions=["Choose startup viewport"])
        _requirement(tmp_path)
        planner.payload = {
            "tasks": [
                {
                    "title": "Implement startup viewport",
                    "description": "Apply the chosen startup framing.",
                    "owner_agent": "design",
                    "depends_on": ["DECISION_GATE: visual_style_startup_pause_viewport"],
                    "acceptance_criteria": ["Startup viewport matches the selected direction."],
                },
            ],
            "decision_gate": {
                "items": [
                    {
                        "id": "startup_viewport",
                        "question": "Which startup viewport should the MVP use?",
                        "context": "Meeting raised visual framing ambiguity.",
                        "options": ["tight", "wide"],
                    },
                ],
            },
        }

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["tasks"][0].depends_on_task_ids == []
        assert result["tasks"][0].status == "preview"

    @staticmethod
    def test_ignores_decision_colon_dependency_when_gate_exists(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path, pending_user_decisions=["Choose retro style"])
        _requirement(tmp_path)
        planner.payload = {
            "tasks": [
                {
                    "title": "Implement retro visual style",
                    "description": "Apply the selected retro style reference.",
                    "owner_agent": "design",
                    "depends_on": ["DECISION: retro_style_reference"],
                    "acceptance_criteria": ["Visual style matches the selected reference."],
                },
            ],
            "decision_gate": {
                "items": [
                    {
                        "id": "retro_style_reference",
                        "question": "Which retro arcade style should the MVP use?",
                        "context": "Meeting raised visual style ambiguity.",
                        "options": ["Game Boy", "NES", "CRT"],
                    },
                ],
            },
        }

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["tasks"][0].depends_on_task_ids == []
        assert result["tasks"][0].status == "preview"

    @staticmethod
    def test_generates_gate_item_ids_when_planner_omits_them(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path, pending_user_decisions=["Choose art direction"])
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "question": "Which art style should the MVP use?",
                    "context": "Meeting conflict",
                    "options": ["retro", "minimal"],
                },
            ],
        )

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["decision_gate"] is not None
        assert len(result["decision_gate"].items) == 1
        assert result["decision_gate"].items[0].id
        assert result["decision_gate"].items[0].question == "Which art style should the MVP use?"

    @staticmethod
    def test_returns_existing_plan_without_reinvoking_planner(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)

        first = svc.generate_plan("meet_001", "proj_001")
        second = svc.generate_plan("meet_001", "proj_001")

        assert second["plan"].id == first["plan"].id
        assert len(planner.calls) == 1


class TestResolveGate:
    @staticmethod
    def test_promotes_preview_tasks_and_stamps_versions(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")

        result = svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})

        assert result["gate"].status == "resolved"
        assert result["gate"].resolution_version == 1
        assert result["plan"].status == "active"
        assert result["plan"].decision_resolution_version == 1

        ws = StudioWorkspace(tmp_path)
        tasks = [ws.delivery_tasks.get(task.id) for task in generated["tasks"]]
        assert tasks[0].status == "ready"
        assert tasks[0].decision_resolution_version == 1
        assert tasks[1].status == "blocked"
        assert tasks[1].decision_resolution_version == 1


    @staticmethod
    def test_generate_plan_saves_assumptions_and_starts_active(
        tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
        _requirement(tmp_path)
        planner = FakePlanner(
            _planner_payload(
                gate_items=[
                    {
                        "id": "visual_style",
                        "question": "Which visual style?",
                        "context": "Ordinary preference",
                        "options": ["pixel", "minimal"],
                    }
                ],
            )
            | {
                "assumptions": [
                    {
                        "category": "art",
                        "decision": "Default to retro pixel art.",
                        "rationale": "Readable and low-cost for Snake MVP.",
                        "impact": "Art, dev, and QA use pixel style.",
                        "owner_agent": "art",
                    }
                ],
                "needs_attention": [],
            }
        )
        svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "active"
        assert result["decision_gate"] is None
        assumptions = StudioWorkspace(tmp_path).project_assumptions.list_all()
        assert assumptions[0].decision == "Default to retro pixel art."
        doc_tasks = [t for t in result["tasks"] if "documentation" in t.title.lower()]
        assert len(doc_tasks) == 1

    @staticmethod
    def test_generate_plan_can_use_legacy_decision_gate_when_enabled(
        tmp_path: Path, monkeypatch,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
        _requirement(tmp_path)
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        planner = FakePlanner(
            _planner_payload(
                gate_items=[
                    {
                        "id": "visual_style",
                        "question": "Which visual style?",
                        "context": "Legacy gate enabled",
                        "options": ["pixel", "minimal"],
                    }
                ],
            )
            | {"assumptions": [], "needs_attention": []}
        )
        svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "awaiting_user_decision"
        assert result["decision_gate"] is not None

    @staticmethod
    def test_generate_plan_creates_needs_attention_plan_for_blockers(
        tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner = FakePlanner({
            "tasks": [],
            "decision_gate": {"items": []},
            "assumptions": [],
            "needs_attention": [
                {
                    "blocker": "Missing required external API key.",
                    "evidence": ["No API key was present in project config."],
                    "recommended_action": "Provide an API key and retry Delivery.",
                    "affected_task_titles": [],
                    "resumable": True,
                }
            ],
        })
        svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "needs_attention"
        assert result["tasks"] == []
        assert result["decision_gate"] is None
        items = StudioWorkspace(tmp_path).needs_attention_items.list_all()
        assert len(items) == 1
        assert items[0].blocker == "Missing required external API key."

    @staticmethod
    def test_generate_plan_demotes_ordinary_preference_needs_attention_to_assumption(
        tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path, pending_user_decisions=["Choose visual style"])
        _requirement(tmp_path)
        planner = FakePlanner({
            "tasks": [
                {
                    "title": "Implement Sokoban visuals",
                    "description": "Build readable default tile visuals for the Sokoban MVP.",
                    "owner_agent": "art",
                    "depends_on": ["DECISION_GATE: visual_style"],
                    "acceptance_criteria": ["Tiles, walls, boxes, goals, and player are visually distinct."],
                },
            ],
            "decision_gate": {
                "items": [
                    {
                        "id": "visual_style",
                        "question": "Which visual style should the MVP use?",
                        "context": "Ordinary delivery preference.",
                        "options": ["pixel", "minimal"],
                    },
                ],
            },
            "assumptions": [],
            "needs_attention": [
                {
                    "blocker": "视觉风格决策门需要用户选择，否则art agent无法开始视觉资源制作",
                    "evidence": [
                        "decision_gate.items[0]: 视觉风格决策门",
                        "tasks[3].title: 视觉资源制作 - 依赖视觉风格决策",
                    ],
                    "recommended_action": "用户需要回答决策门中的视觉风格问题，art agent才能开始工作",
                    "affected_task_titles": ["Implement Sokoban visuals"],
                    "resumable": True,
                }
            ],
        })
        svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "active"
        assert result["tasks"]
        assert result["decision_gate"] is None
        ws = StudioWorkspace(tmp_path)
        assert ws.needs_attention_items.list_all() == []
        assumptions = ws.project_assumptions.list_all()
        assert len(assumptions) == 1
        assert "视觉风格" in assumptions[0].decision

    @staticmethod
    @pytest.mark.parametrize(
        ("blocker", "evidence", "recommended_action"),
        [
            (
                "项目目录为空，缺少项目结构和基础配置",
                ["项目目录扫描结果：空目录"],
                "Dev agent should create the initial HTML, JavaScript, docs, and project structure.",
            ),
            (
                "Art agent和Dev agent尚未参与项目讨论，缺乏技术和艺术维度的专业输入",
                ["meeting supplementary.missing_participants: art agent and dev agent were absent"],
                "Continue Delivery and let the assigned art/dev tasks provide those inputs.",
            ),
            (
                "localStorage unavailable fallback strategy needs a default",
                ["Browser storage fallback can be implemented by the dev task."],
                "Use an in-memory fallback and document that saves are disabled when storage is unavailable.",
            ),
        ],
    )
    def test_generate_plan_demotes_delivery_context_warnings_to_assumptions(
        tmp_path: Path,
        blocker: str,
        evidence: list[str],
        recommended_action: str,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner = FakePlanner({
            "tasks": [
                {
                    "title": "Implement Sokoban MVP",
                    "description": "Create a playable Sokoban MVP from an empty project directory.",
                    "owner_agent": "dev",
                    "depends_on": [],
                    "acceptance_criteria": ["The game opens in a browser and can be played."],
                },
            ],
            "decision_gate": {"items": []},
            "assumptions": [],
            "needs_attention": [
                {
                    "blocker": blocker,
                    "evidence": evidence,
                    "recommended_action": recommended_action,
                    "affected_task_titles": ["Implement Sokoban MVP"],
                    "resumable": True,
                }
            ],
        })
        svc = DeliveryPlanService(tmp_path, planner=planner, project_root=tmp_path.parent)

        result = svc.generate_plan("meet_001", "proj_001")

        assert result["plan"].status == "active"
        assert len(result["tasks"]) == 2  # planner task + auto-added documentation task
        ws = StudioWorkspace(tmp_path)
        assert ws.needs_attention_items.list_all() == []
        assumptions = ws.project_assumptions.list_all()
        assert len(assumptions) == 1
        assert blocker in assumptions[0].decision

    @staticmethod
    def test_board_status_prefers_repairing_plan_over_open_needs_attention(
        tmp_path: Path,
    ) -> None:
        ws = StudioWorkspace(tmp_path)
        ws.ensure_layout()
        ws.delivery_plans.save(
            DeliveryPlan(
                id="plan_001",
                meeting_id="meet_001",
                requirement_id="req_001",
                project_id="proj_001",
                status="repairing",
            )
        )
        ws.needs_attention_items.save(
            NeedsAttentionItem(
                id="needs_001",
                requirement_id="req_001",
                project_id="proj_001",
                plan_id="plan_001",
                blocker="Ordinary preference needs a default.",
                evidence=["Planner recorded a pending preference."],
                recommended_action="Proceed with the documented default.",
            )
        )

        result = DeliveryPlanService(tmp_path, project_root=tmp_path.parent).list_board(
            requirement_id="req_001",
        )

        assert result["runner_status"] == "repairing"


class TestStartTask:
    @staticmethod
    def test_rejects_preview_task_before_gate_resolution(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")

        with pytest.raises(ValueError, match="not ready"):
            svc.start_task(generated["tasks"][0].id)

    @staticmethod
    def test_uses_server_side_project_session_lookup(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        generated = svc.generate_plan("meet_001", "proj_001")
        _create_session(tmp_path, project_id="proj_001", agent="design", session_id="sess_design_123")

        task = svc.start_task(generated["tasks"][0].id)

        assert task.status == "in_progress"
        lease = StudioWorkspace(tmp_path).session_leases.get("proj_001_design")
        assert lease.session_id == "sess_design_123"

    @staticmethod
    def test_rejects_missing_project_session(
        svc: DeliveryPlanService, tmp_path: Path,
    ) -> None:
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        generated = svc.generate_plan("meet_001", "proj_001")

        with pytest.raises(ValueError, match="no session found"):
            svc.start_task(generated["tasks"][0].id)

    @staticmethod
    def test_rejects_missing_task_decision_version_after_gate_resolution(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")
        svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})
        _create_session(tmp_path, project_id="proj_001", agent="design")

        ws = StudioWorkspace(tmp_path)
        task = ws.delivery_tasks.get(generated["tasks"][0].id)
        ws.delivery_tasks.save(task.model_copy(update={"decision_resolution_version": None}))

        with pytest.raises(ValueError, match="decision_resolution_version"):
            svc.start_task(task.id)

    @staticmethod
    def test_bug_fix_task_inherits_resolved_decision_version(
        tmp_path: Path,
    ) -> None:
        ws = StudioWorkspace(tmp_path)
        ws.ensure_layout()
        ws.delivery_plans.save(
            DeliveryPlan(
                id="plan_001",
                meeting_id="meet_001",
                requirement_id="req_001",
                project_id="proj_001",
                status="validating",
                decision_gate_id="gate_001",
                decision_resolution_version=1,
            )
        )
        ws.decision_gates.save(
            KickoffDecisionGate(
                id="gate_001",
                plan_id="plan_001",
                meeting_id="meet_001",
                requirement_id="req_001",
                project_id="proj_001",
                status="resolved",
                resolution_version=1,
                items=[
                    GateItem(
                        id="visual_style",
                        question="Which visual style?",
                        context="Legacy gate",
                        options=["pixel", "minimal"],
                        resolution="pixel",
                    )
                ],
            )
        )
        _create_session(tmp_path, project_id="proj_001", agent="dev", session_id="sess_dev_001")
        svc = DeliveryPlanService(tmp_path, project_root=tmp_path.parent)

        [bug_task] = svc.create_bug_fix_tasks(
            "plan_001",
            [
                {
                    "criterion_id": "crit_launch",
                    "repair_hint": "Fix validation failure for startup command.",
                    "owner_hint": "dev",
                }
            ],
        )

        assert bug_task.decision_resolution_version == 1
        started = svc.start_task(bug_task.id)
        assert started.status == "in_progress"

    @staticmethod
    def test_rejects_stale_task_decision_version(
        svc: DeliveryPlanService, planner: FakePlanner, tmp_path: Path, monkeypatch,
    ) -> None:
        monkeypatch.setenv("GAME_STUDIO_ENABLE_DELIVERY_DECISION_GATE", "true")
        _completed_meeting(tmp_path)
        _requirement(tmp_path)
        planner.payload = _planner_payload(
            gate_items=[
                {
                    "id": "scope_direction",
                    "question": "Ship status effects in MVP?",
                    "context": "Meeting conflict",
                    "options": ["yes", "no"],
                },
            ],
        )
        generated = svc.generate_plan("meet_001", "proj_001")
        svc.resolve_gate(generated["decision_gate"].id, {"scope_direction": "no"})
        _create_session(tmp_path, project_id="proj_001", agent="design")

        ws = StudioWorkspace(tmp_path)
        task = ws.delivery_tasks.get(generated["tasks"][0].id)
        ws.delivery_tasks.save(task.model_copy(update={"decision_resolution_version": 0}))

        with pytest.raises(ValueError, match="decision_resolution_version"):
            svc.start_task(task.id)
