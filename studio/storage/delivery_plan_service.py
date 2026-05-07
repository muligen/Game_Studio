from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Protocol
from uuid import uuid4

from studio.agents.delivery_planner import DeliveryPlannerAgent
from studio.agents.profile_loader import AgentProfileLoader
from studio.schemas.delivery import (
    DeliveryPlan,
    DeliveryTask,
    GateItem,
    KickoffDecisionGate,
    TaskExecutionResult,
)
from studio.schemas.delivery_events import DeliveryTaskEvent
from studio.storage.git_tracker import GitTracker
from studio.storage.session_lease import SessionLeaseManager
from studio.storage.workspace import StudioWorkspace

VALID_OWNER_AGENTS = frozenset({"design", "dev", "qa", "art", "reviewer", "quality"})
OWNER_AGENT_ALIASES = {
    "design_agent": "design",
    "dev_agent": "dev",
    "qa_agent": "qa",
    "art_agent": "art",
    "reviewer_agent": "reviewer",
    "quality_agent": "quality",
    "moderator": "quality",
    "moderator_agent": "quality",
    "product_manager": "design",
    "pm": "design",
    "manager": "design",
}
_FALLBACK_OWNER_AGENT = "dev"


class DeliveryPlannerProtocol(Protocol):
    def generate(self, context: dict[str, object]) -> dict[str, object]:
        ...


class ClaudeDeliveryPlanner:
    def __init__(self, *, project_root: Path | None = None) -> None:
        self._agent = DeliveryPlannerAgent(project_root=project_root)

    def generate(self, context: dict[str, object]) -> dict[str, object]:
        return self._agent.generate_payload(context)


class DeliveryPlanService:
    """Core service that orchestrates plan generation, gate resolution, and task starting."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        planner: DeliveryPlannerProtocol | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._ws = StudioWorkspace(workspace_root)
        self._ws.ensure_layout()
        self._lease_mgr = SessionLeaseManager(workspace_root)
        resolved_project_root = project_root or (
            workspace_root.parent if workspace_root.name == ".studio-data" else None
        )
        self._project_root = resolved_project_root or Path.cwd()
        self._planner = planner or ClaudeDeliveryPlanner(project_root=resolved_project_root)

    def generate_plan(self, meeting_id: str, project_id: str) -> dict:
        meeting = self._ws.meetings.get(meeting_id)
        if meeting.status != "completed":
            raise ValueError(f"meeting {meeting_id} is not completed (status={meeting.status})")

        existing_plans = [
            p for p in self._ws.delivery_plans.list_all() if p.meeting_id == meeting_id
        ]
        if existing_plans:
            plan = existing_plans[0]
            tasks = [t for t in self._ws.delivery_tasks.list_all() if t.plan_id == plan.id]
            gate: KickoffDecisionGate | None = None
            if plan.decision_gate_id:
                gate = self._ws.decision_gates.get(plan.decision_gate_id)
            return {"plan": plan, "tasks": tasks, "decision_gate": gate}

        requirement = self._ws.requirements.get(str(meeting.requirement_id))
        design_docs = [
            doc.model_dump()
            for doc in self._ws.design_docs.list_all()
            if doc.requirement_id == requirement.id
        ]
        project_sessions = [
            session.model_dump()
            for session in self._ws.sessions.list_all()
            if session.project_id == project_id
        ]
        planning_context = {
            "meeting": meeting.model_dump(),
            "requirement": requirement.model_dump(),
            "design_docs": design_docs,
            "project_sessions": project_sessions,
            "pending_user_decision_candidates": list(meeting.pending_user_decisions),
            "project_id": project_id,
            "goal": {
                "project_id": project_id,
                "project_dir": str(
                    GitTracker(repo_root=self._project_root, project_id=project_id).ensure_project_dir()
                ),
                "phase": "delivery_planning",
            },
        }
        planner_output = self._planner.generate(planning_context)
        raw_tasks = planner_output.get("tasks", [])
        if not raw_tasks:
            raise ValueError("delivery planner returned no tasks")

        for raw in raw_tasks:
            owner = self._normalize_owner_agent(raw.get("owner_agent", ""))
            if owner not in VALID_OWNER_AGENTS:
                original = raw.get("owner_agent", "")
                logging.getLogger(__name__).warning(
                    "Unknown owner_agent '%s', falling back to '%s'", original, _FALLBACK_OWNER_AGENT,
                )
                owner = _FALLBACK_OWNER_AGENT
            raw["owner_agent"] = owner

        task_id_map: dict[str, str] = {}
        for raw in raw_tasks:
            tid = f"task_{uuid4().hex}"
            task_id_map[str(raw["title"])] = tid

        gate_items_data = planner_output.get("decision_gate", {}).get("items", [])
        has_gate = bool(gate_items_data)
        dep_graph: dict[str, list[str]] = {}
        for raw in raw_tasks:
            tid = task_id_map[str(raw["title"])]
            dep_ids: list[str] = []
            for title in raw.get("depends_on", []):
                if title not in task_id_map:
                    if has_gate and self._is_decision_placeholder(str(title)):
                        continue
                    raise ValueError(f"depends_on references unknown task '{title}'")
                dep_ids.append(task_id_map[title])
            dep_graph[tid] = dep_ids

        if self._has_cycle(dep_graph):
            raise ValueError("task dependency graph contains a cycle")

        plan_id = f"plan_{uuid4().hex}"
        plan = DeliveryPlan(
            id=plan_id,
            meeting_id=meeting_id,
            requirement_id=requirement.id,
            project_id=project_id,
            status="awaiting_user_decision" if has_gate else "active",
        )

        saved_tasks: list[DeliveryTask] = []
        for raw in raw_tasks:
            tid = task_id_map[str(raw["title"])]
            dep_ids = dep_graph[tid]
            task = DeliveryTask(
                id=tid,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=requirement.id,
                project_id=project_id,
                title=str(raw["title"]),
                description=str(raw.get("description", "")),
                owner_agent=str(raw["owner_agent"]),
                status="preview" if has_gate else ("blocked" if dep_ids else "ready"),
                depends_on_task_ids=dep_ids,
                acceptance_criteria=[str(item) for item in raw.get("acceptance_criteria", [])],
            )
            self._ws.delivery_tasks.save(task)
            saved_tasks.append(task)
            plan.task_ids.append(tid)

        saved_gate: KickoffDecisionGate | None = None
        if has_gate:
            gate_id = f"gate_{uuid4().hex}"
            gate_items = [
                GateItem(
                    id=self._gate_item_id(item, index),
                    question=str(item["question"]),
                    context=str(item.get("context", "")),
                    options=[str(option) for option in item["options"]],
                )
                for index, item in enumerate(gate_items_data, start=1)
            ]
            saved_gate = KickoffDecisionGate(
                id=gate_id,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=requirement.id,
                project_id=project_id,
                items=gate_items,
            )
            self._ws.decision_gates.save(saved_gate)
            plan.decision_gate_id = gate_id

        self._ws.delivery_plans.save(plan)
        return {"plan": plan, "tasks": saved_tasks, "decision_gate": saved_gate}

    def resolve_gate(self, gate_id: str, resolutions: dict[str, str]) -> dict:
        gate = self._ws.decision_gates.get(gate_id)
        if gate.status != "open":
            raise ValueError(f"gate {gate_id} is not open (status={gate.status})")

        for item in gate.items:
            if item.id not in resolutions:
                raise ValueError(f"gate item '{item.id}' has no resolution")
            if resolutions[item.id] not in item.options:
                raise ValueError(
                    f"resolution '{resolutions[item.id]}' is not a valid option for item '{item.id}'"
                )

        next_version = gate.resolution_version + 1
        updated_items = [
            item.model_copy(update={"resolution": resolutions[item.id]})
            for item in gate.items
        ]
        gate = gate.model_copy(
            update={
                "status": "resolved",
                "resolution_version": next_version,
                "items": updated_items,
            }
        )
        self._ws.decision_gates.save(gate)

        plan = self._ws.delivery_plans.get(gate.plan_id)
        plan = plan.model_copy(
            update={
                "status": "active",
                "decision_resolution_version": next_version,
            }
        )
        self._ws.delivery_plans.save(plan)

        for task_id in plan.task_ids:
            task = self._ws.delivery_tasks.get(task_id)
            next_status = "blocked" if task.depends_on_task_ids else "ready"
            updated_task = task.model_copy(
                update={
                    "status": next_status,
                    "decision_resolution_version": next_version,
                }
            )
            self._ws.delivery_tasks.save(updated_task)

        return {"gate": gate, "plan": plan}

    def start_task(self, task_id: str) -> DeliveryTask:
        task = self._ws.delivery_tasks.get(task_id)
        if task.status != "ready":
            raise ValueError(f"task {task_id} is not ready (status={task.status})")

        plan = self._ws.delivery_plans.get(task.plan_id)
        if plan.status != "active":
            raise ValueError(f"plan {plan.id} is not active (status={plan.status})")

        if plan.decision_gate_id:
            gate = self._ws.decision_gates.get(plan.decision_gate_id)
            if gate.status != "resolved":
                raise ValueError(
                    f"plan {plan.id} has an unresolved decision gate (status={gate.status})"
                )
            if task.decision_resolution_version is None:
                raise ValueError(
                    f"task {task_id} decision_resolution_version is missing while plan "
                    f"{plan.id} requires version {plan.decision_resolution_version}"
                )
            if task.decision_resolution_version != plan.decision_resolution_version:
                raise ValueError(
                    f"task {task_id} decision_resolution_version ({task.decision_resolution_version}) "
                    f"does not match plan ({plan.decision_resolution_version})"
                )

        for dep_id in task.depends_on_task_ids:
            dep_task = self._ws.delivery_tasks.get(dep_id)
            if dep_task.status != "done":
                raise ValueError(
                    f"dependency task {dep_id} is not done (status={dep_task.status})"
                )

        composite_key = f"{task.project_id}_{task.owner_agent}"
        try:
            session = self._ws.sessions.get(composite_key)
        except FileNotFoundError as exc:
            raise ValueError(f"no session found for {composite_key}") from exc
        if not session.project_dir or not session.agent_config_dir:
            project_dir = GitTracker(repo_root=self._project_root, project_id=task.project_id).ensure_project_dir()
            agent_config_dir = session.agent_config_dir
            if not agent_config_dir:
                try:
                    agent_config_dir = str(AgentProfileLoader().load(task.owner_agent).claude_project_root)
                except Exception:
                    agent_config_dir = None
            session = session.model_copy(
                update={
                    "project_dir": session.project_dir or str(project_dir),
                    "agent_config_dir": agent_config_dir,
                }
            )
            self._ws.sessions.save(session)

        if not self._lease_mgr.is_available(task.project_id, task.owner_agent):
            raise ValueError(
                f"session lease for {task.project_id}/{task.owner_agent} is not available"
            )

        self._lease_mgr.acquire(
            project_id=task.project_id,
            agent=task.owner_agent,
            task_id=task_id,
            session_id=session.session_id,
        )
        task = task.model_copy(
            update={
                "status": "in_progress",
                "attempt_count": task.attempt_count + 1,
                "last_error": None,
                "last_failed_at": None,
            }
        )
        self._ws.delivery_tasks.save(task)
        return task

    def complete_task(
        self,
        task_id: str,
        summary: str,
        *,
        output_artifact_ids: list[str] | None = None,
        changed_files: list[str] | None = None,
        tests_or_checks: list[str] | None = None,
        follow_up_notes: list[str] | None = None,
        dependency_context_used: list[str] | None = None,
        decision_context_used: list[str] | None = None,
        context_warnings: list[str] | None = None,
    ) -> dict:
        task = self._ws.delivery_tasks.get(task_id)
        if task.status != "in_progress":
            raise ValueError(f"task {task_id} is not in_progress (status={task.status})")

        plan = self._ws.delivery_plans.get(task.plan_id)
        lease = self._lease_mgr.find(task.project_id, task.owner_agent)
        session_id = lease.session_id if lease else ""
        exec_result = TaskExecutionResult(
            id=f"result_{task_id}",
            task_id=task_id,
            plan_id=task.plan_id,
            project_id=task.project_id,
            agent=task.owner_agent,
            session_id=session_id,
            summary=summary,
            output_artifact_ids=output_artifact_ids or [],
            changed_files=changed_files or [],
            tests_or_checks=tests_or_checks or [],
            follow_up_notes=follow_up_notes or [],
            dependency_context_used=dependency_context_used or [],
            decision_context_used=decision_context_used or [],
            context_warnings=context_warnings or [],
        )
        self._ws.execution_results.save(exec_result)

        now = datetime.now(UTC).isoformat()
        task = task.model_copy(
            update={
                "status": "done",
                "execution_result_id": exec_result.id,
                "output_artifact_ids": exec_result.output_artifact_ids,
                "updated_at": now,
            }
        )
        self._ws.delivery_tasks.save(task)

        self._lease_mgr.release(task.project_id, task.owner_agent)

        for candidate_id in plan.task_ids:
            candidate = self._ws.delivery_tasks.get(candidate_id)
            if candidate.status == "blocked" and all(
                self._ws.delivery_tasks.get(dep_id).status == "done"
                for dep_id in candidate.depends_on_task_ids
            ):
                self._ws.delivery_tasks.save(
                    candidate.model_copy(update={"status": "ready", "updated_at": now})
                )

        refreshed_tasks = [self._ws.delivery_tasks.get(candidate_id) for candidate_id in plan.task_ids]
        if all(candidate.status == "done" for candidate in refreshed_tasks):
            plan = plan.model_copy(update={"status": "completed", "updated_at": now})
            self._ws.delivery_plans.save(plan)

            try:
                req = self._ws.requirements.get(plan.requirement_id)
                if req.status != "done":
                    from studio.domain.requirement_flow import transition_requirement
                    req = transition_requirement(req, "done")
                    self._ws.requirements.save(req)
            except Exception:
                logger = logging.getLogger(__name__)
                logger.exception("Failed to auto-advance requirement %s", plan.requirement_id)

        return {"task": task, "execution_result": exec_result}

    def fail_task(
        self,
        task_id: str,
        *,
        error_message: str,
        exception_type: str | None = None,
        traceback_excerpt: str | None = None,
    ) -> dict:
        task = self._ws.delivery_tasks.get(task_id)
        if task.status not in {"ready", "in_progress"}:
            raise ValueError(f"task {task_id} cannot fail from status={task.status}")

        attempt = task.attempt_count or 1
        result_id = f"result_{task_id}_attempt_{attempt}"
        lease = self._lease_mgr.find(task.project_id, task.owner_agent)
        session_id = lease.session_id if lease else "unavailable"
        exec_result = TaskExecutionResult(
            id=result_id,
            task_id=task_id,
            plan_id=task.plan_id,
            project_id=task.project_id,
            agent=task.owner_agent,
            session_id=session_id,
            summary=f"{task.owner_agent} failed: {task.title}",
            follow_up_notes=["Retry the task after reviewing the error."],
            context_warnings=["delivery task failed before completion"],
            error_message=error_message,
            exception_type=exception_type,
            traceback_excerpt=traceback_excerpt,
        )
        self._ws.execution_results.save(exec_result)

        now = datetime.now(UTC).isoformat()
        task = task.model_copy(
            update={
                "status": "failed",
                "execution_result_id": exec_result.id,
                "last_error": error_message,
                "last_failed_at": now,
                "updated_at": now,
            }
        )
        self._ws.delivery_tasks.save(task)

        if lease is not None and lease.status == "held":
            self._lease_mgr.release(task.project_id, task.owner_agent)

        return {"task": task, "execution_result": exec_result}

    def retry_task(self, task_id: str) -> DeliveryTask:
        task = self._ws.delivery_tasks.get(task_id)
        if task.status != "failed":
            raise ValueError(f"task {task_id} is not failed (status={task.status})")

        plan = self._ws.delivery_plans.get(task.plan_id)
        if plan.status != "active":
            raise ValueError(f"plan {plan.id} is not active (status={plan.status})")

        for dep_id in task.depends_on_task_ids:
            dep_task = self._ws.delivery_tasks.get(dep_id)
            if dep_task.status != "done":
                raise ValueError(
                    f"dependency task {dep_id} is not done (status={dep_task.status})"
                )

        lease = self._lease_mgr.find(task.project_id, task.owner_agent)
        if lease is not None and lease.status == "held":
            self._lease_mgr.release(task.project_id, task.owner_agent)

        retried = task.model_copy(
            update={
                "status": "ready",
                "execution_result_id": None,
                "output_artifact_ids": [],
                "last_error": None,
                "last_failed_at": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._ws.delivery_tasks.save(retried)
        return retried

    def record_task_event(
        self,
        task_id: str,
        event_type: str,
        *,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> DeliveryTaskEvent:
        task = self._ws.delivery_tasks.get(task_id)
        event_count = len([
            event for event in self._ws.delivery_task_events.list_all()
            if event.task_id == task_id
        ])
        event = DeliveryTaskEvent(
            id=f"evt_{task_id}_{event_count + 1:04d}",
            task_id=task.id,
            plan_id=task.plan_id,
            requirement_id=task.requirement_id,
            project_id=task.project_id,
            agent=task.owner_agent,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
        return self._ws.delivery_task_events.save(event)

    def list_board(self, requirement_id: str | None = None) -> dict:
        plans = self._ws.delivery_plans.list_all()
        tasks = self._ws.delivery_tasks.list_all()
        gates = self._ws.decision_gates.list_all()

        if requirement_id:
            plans = [plan for plan in plans if plan.requirement_id == requirement_id]
            plan_ids = {plan.id for plan in plans}
            tasks = [task for task in tasks if task.plan_id in plan_ids]
            gates = [gate for gate in gates if gate.plan_id in plan_ids]

        return {
            "plans": plans,
            "tasks": tasks,
            "decision_gates": gates,
            "runner_status": self._runner_status(plans, tasks, gates),
        }

    @staticmethod
    def _runner_status(
        plans: list[DeliveryPlan],
        tasks: list[DeliveryTask],
        gates: list[KickoffDecisionGate],
    ) -> str:
        if not plans:
            return "idle"
        if any(gate.status == "open" for gate in gates):
            return "waiting_for_decision"
        if any(plan.status == "completed" for plan in plans) and all(
            task.status == "done" for task in tasks
        ):
            return "completed"
        if any(task.status == "failed" for task in tasks):
            return "failed"
        if any(task.status == "in_progress" for task in tasks):
            return "running"
        if any(plan.status == "active" for plan in plans):
            return "running"
        return "idle"

    @staticmethod
    def _gate_item_id(item: dict[str, object], index: int) -> str:
        raw_id = item.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            return raw_id.strip()

        question = str(item.get("question", "")).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", question).strip("_")
        if slug:
            return f"{slug}_{index}"[:64]
        return f"gate_item_{index}"

    @staticmethod
    def _normalize_owner_agent(owner: object) -> str:
        normalized = str(owner).strip().lower()
        return OWNER_AGENT_ALIASES.get(normalized, normalized)

    @staticmethod
    def _is_decision_placeholder(value: str) -> bool:
        normalized = value.strip().upper()
        return (
            normalized.startswith("STAKEHOLDER_DECISION")
            or normalized.startswith("USER_DECISION")
            or normalized.startswith("DECISION:")
            or normalized.startswith("DECISION_")
            or normalized.startswith("DECISION_GATE")
        )

    def _has_cycle(self, graph: dict[str, list[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in graph.get(node, []):
                if visit(dep):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)
