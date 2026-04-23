from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from studio.schemas.delivery import (
    DeliveryPlan,
    DeliveryTask,
    GateItem,
    KickoffDecisionGate,
)
from studio.storage.session_lease import SessionLeaseManager
from studio.storage.workspace import StudioWorkspace

VALID_OWNER_AGENTS = frozenset({"design", "dev", "qa", "art", "reviewer", "quality"})


class DeliveryPlanService:
    """Core service that orchestrates plan generation, gate resolution, and task starting."""

    def __init__(self, workspace_root: Path) -> None:
        self._ws = StudioWorkspace(workspace_root)
        self._ws.ensure_layout()
        self._lease_mgr = SessionLeaseManager(workspace_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_plan(
        self,
        meeting_id: str,
        planner_output: dict,
        project_id: str,
    ) -> dict:
        """Create a DeliveryPlan from planner output.

        Parameters
        ----------
        meeting_id : str
            ID of the completed meeting to plan from.
        planner_output : dict
            Planner output containing ``tasks`` and optionally ``decision_gate``.
        project_id : str
            Project this plan belongs to.

        Returns
        -------
        dict
            ``{"plan": DeliveryPlan, "tasks": list[DeliveryTask], "decision_gate": KickoffDecisionGate | None}``

        Raises
        ------
        ValueError
            If the meeting is not completed, contains unknown owners, or has cycles.
        FileNotFoundError
            If the meeting does not exist.
        """
        # Load and validate meeting
        meeting = self._ws.meetings.get(meeting_id)
        if meeting.status != "completed":
            raise ValueError(f"meeting {meeting_id} is not completed (status={meeting.status})")

        # Check for existing plan for this meeting
        existing_plans = [
            p for p in self._ws.delivery_plans.list_all() if p.meeting_id == meeting_id
        ]
        if existing_plans:
            plan = existing_plans[0]
            tasks = [
                t for t in self._ws.delivery_tasks.list_all() if t.plan_id == plan.id
            ]
            gate: KickoffDecisionGate | None = None
            if plan.decision_gate_id:
                gate = self._ws.decision_gates.get(plan.decision_gate_id)
            return {"plan": plan, "tasks": tasks, "decision_gate": gate}

        requirement_id = str(meeting.requirement_id)

        # Validate owner_agent values
        raw_tasks = planner_output.get("tasks", [])
        for raw in raw_tasks:
            owner = raw.get("owner_agent", "")
            if owner not in VALID_OWNER_AGENTS:
                raise ValueError(
                    f"unknown owner_agent '{owner}'; must be one of {sorted(VALID_OWNER_AGENTS)}"
                )

        # Build title -> temporary-id mapping for dependency resolution
        task_id_map: dict[str, str] = {}
        for raw in raw_tasks:
            tid = f"task_{uuid4().hex}"
            task_id_map[raw["title"]] = tid

        # Resolve depends_on title references to task IDs and build dep graph
        dep_graph: dict[str, list[str]] = {}
        for raw in raw_tasks:
            tid = task_id_map[raw["title"]]
            dep_titles = raw.get("depends_on", [])
            dep_ids = []
            for title in dep_titles:
                if title not in task_id_map:
                    raise ValueError(f"depends_on references unknown task '{title}'")
                dep_ids.append(task_id_map[title])
            dep_graph[tid] = dep_ids

        # Detect cycles
        if self._has_cycle(dep_graph):
            raise ValueError("task dependency graph contains a cycle")

        # Create the DeliveryPlan record
        plan_id = f"plan_{uuid4().hex}"
        plan = DeliveryPlan(
            id=plan_id,
            meeting_id=meeting_id,
            requirement_id=requirement_id,
            project_id=project_id,
        )

        # Create DeliveryTask records
        saved_tasks: list[DeliveryTask] = []
        for raw in raw_tasks:
            tid = task_id_map[raw["title"]]
            dep_ids = dep_graph[tid]
            has_deps = len(dep_ids) > 0
            task = DeliveryTask(
                id=tid,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=requirement_id,
                project_id=project_id,
                title=raw["title"],
                description=raw.get("description", ""),
                owner_agent=raw["owner_agent"],
                status="blocked" if has_deps else "ready",
                depends_on_task_ids=dep_ids,
                acceptance_criteria=raw.get("acceptance_criteria", []),
            )
            self._ws.delivery_tasks.save(task)
            saved_tasks.append(task)
            plan.task_ids.append(tid)

        # Create KickoffDecisionGate if present
        gate_items_data = planner_output.get("decision_gate", {}).get("items", [])
        saved_gate: KickoffDecisionGate | None = None
        if gate_items_data:
            gate_id = f"gate_{uuid4().hex}"
            gate_items = [
                GateItem(
                    id=item["id"],
                    question=item["question"],
                    context=item.get("context", ""),
                    options=item["options"],
                )
                for item in gate_items_data
            ]
            saved_gate = KickoffDecisionGate(
                id=gate_id,
                plan_id=plan_id,
                meeting_id=meeting_id,
                requirement_id=requirement_id,
                project_id=project_id,
                items=gate_items,
            )
            self._ws.decision_gates.save(saved_gate)
            plan.decision_gate_id = gate_id
            plan.status = "awaiting_user_decision"
        else:
            plan.status = "active"

        self._ws.delivery_plans.save(plan)

        return {"plan": plan, "tasks": saved_tasks, "decision_gate": saved_gate}

    def resolve_gate(self, gate_id: str, resolutions: dict[str, str]) -> dict:
        """Resolve a KickoffDecisionGate and activate the associated plan.

        Parameters
        ----------
        gate_id : str
            ID of the gate to resolve.
        resolutions : dict[str, str]
            Mapping of gate item ID -> chosen resolution (must be one of the item's options).

        Returns
        -------
        dict
            ``{"gate": KickoffDecisionGate, "plan": DeliveryPlan}``
        """
        gate = self._ws.decision_gates.get(gate_id)

        if gate.status != "open":
            raise ValueError(f"gate {gate_id} is not open (status={gate.status})")

        # Validate all items have resolutions with valid options
        for item in gate.items:
            if item.id not in resolutions:
                raise ValueError(f"gate item '{item.id}' has no resolution")
            if resolutions[item.id] not in item.options:
                raise ValueError(
                    f"resolution '{resolutions[item.id]}' is not a valid option for item '{item.id}'"
                )

        # Apply resolutions
        updated_items = [
            item.model_copy(update={"resolution": resolutions[item.id]})
            for item in gate.items
        ]
        gate = gate.model_copy(
            update={
                "status": "resolved",
                "resolution_version": gate.resolution_version + 1,
                "items": updated_items,
            }
        )
        self._ws.decision_gates.save(gate)

        # Activate the associated plan
        plan = self._ws.delivery_plans.get(gate.plan_id)
        plan = plan.model_copy(
            update={
                "status": "active",
                "decision_resolution_version": gate.resolution_version,
            }
        )
        self._ws.delivery_plans.save(plan)

        return {"gate": gate, "plan": plan}

    def start_task(self, task_id: str, session_id: str) -> DeliveryTask:
        """Start a task, validating preconditions and acquiring a lease.

        Parameters
        ----------
        task_id : str
            ID of the task to start.
        session_id : str
            Session ID to bind to the lease.

        Returns
        -------
        DeliveryTask
            The updated task with status ``"in_progress"``.
        """
        task = self._ws.delivery_tasks.get(task_id)

        if task.status != "ready":
            raise ValueError(f"task {task_id} is not ready (status={task.status})")

        # Load the plan to check gate resolution
        plan = self._ws.delivery_plans.get(task.plan_id)
        if plan.decision_gate_id:
            gate = self._ws.decision_gates.get(plan.decision_gate_id)
            if gate.status != "resolved":
                raise ValueError(
                    f"plan {plan.id} has an unresolved decision gate (status={gate.status})"
                )

        # Validate all dependency tasks are done
        for dep_id in task.depends_on_task_ids:
            dep_task = self._ws.delivery_tasks.get(dep_id)
            if dep_task.status != "done":
                raise ValueError(
                    f"dependency task {dep_id} is not done (status={dep_task.status})"
                )

        # Validate project session exists
        composite_key = f"{task.project_id}_{task.owner_agent}"
        try:
            self._ws.sessions.get(composite_key)
        except FileNotFoundError as exc:
            raise ValueError(
                f"no session found for {composite_key}"
            ) from exc

        # Validate lease is available
        if not self._lease_mgr.is_available(task.project_id, task.owner_agent):
            raise ValueError(
                f"session lease for {task.project_id}/{task.owner_agent} is not available"
            )

        # Acquire lease
        self._lease_mgr.acquire(
            project_id=task.project_id,
            agent=task.owner_agent,
            task_id=task_id,
            session_id=session_id,
        )

        # Update task
        task = task.model_copy(update={"status": "in_progress"})
        self._ws.delivery_tasks.save(task)

        return task

    def list_board(self, requirement_id: str | None = None) -> dict:
        """List all plans, tasks, and decision gates, optionally filtered by requirement.

        Parameters
        ----------
        requirement_id : str | None
            If provided, only return items for this requirement.

        Returns
        -------
        dict
            ``{"plans": list, "tasks": list, "decision_gates": list}``
        """
        plans = self._ws.delivery_plans.list_all()
        tasks = self._ws.delivery_tasks.list_all()
        gates = self._ws.decision_gates.list_all()

        if requirement_id is not None:
            plans = [p for p in plans if p.requirement_id == requirement_id]
            tasks = [t for t in tasks if t.requirement_id == requirement_id]
            gates = [g for g in gates if g.requirement_id == requirement_id]

        return {"plans": plans, "tasks": tasks, "decision_gates": gates}

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_cycle(dep_graph: dict[str, list[str]]) -> bool:
        """Detect cycles in a dependency graph using DFS.

        Parameters
        ----------
        dep_graph : dict[str, list[str]]
            Mapping of node ID -> list of dependency node IDs.

        Returns
        -------
        bool
            ``True`` if a cycle is detected, ``False`` otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in dep_graph}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in dep_graph.get(node, []):
                if neighbor not in color:
                    # Neighbor not in graph; skip (external dep)
                    continue
                if color[neighbor] == GRAY:
                    return True  # cycle found
                if color[neighbor] == WHITE:
                    if dfs(neighbor):
                        return True
            color[node] = BLACK
            return False

        for node in dep_graph:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        return False
