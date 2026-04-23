# Meeting To Delivery Board Merge Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `feature/meeting-to-delivery-board` safe to merge by replacing caller-supplied planner output and placeholder sessions with strict backend planner/session behavior.

**Architecture:** Keep the existing delivery schemas, repositories, service, API route, and standalone frontend board. Tighten the service boundary so the API invokes a planner dependency, unresolved decision gates create non-actionable preview tasks, task start resolves project agent sessions server-side, and `DeliveryPlannerAgent` propagates Claude errors instead of creating fallback plans.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, pytest, React, TypeScript, TanStack Query

---

## File Structure

- `studio/agents/delivery_planner.py`: remove fallback behavior and expose strict payload conversion for service/API use.
- `studio/storage/delivery_plan_service.py`: accept a planner dependency, build planner context from workspace data, create preview tasks behind gates, stamp decision versions, and resolve sessions server-side.
- `studio/api/routes/delivery.py`: remove `planner_output` and `session_id` request fields.
- `web/src/lib/api.ts`: remove planner output and session id from delivery client methods.
- `web/src/pages/DeliveryBoard.tsx`: stop sending `session-placeholder`.
- `tests/test_delivery_planner_agent.py`: assert Claude errors propagate.
- `tests/test_delivery_plan_service.py`: assert planner invocation, gate preview blocking, version stamping, and server-side session lookup.
- `tests/test_delivery_api.py`: assert new request shapes and error behavior.

---

## Tasks

### Task 1: Strict Delivery Planner

- [ ] Change `tests/test_delivery_planner_agent.py` so Claude errors are expected to raise `ClaudeRoleError`.
- [ ] Run `uv run pytest tests/test_delivery_planner_agent.py -q` and confirm the strict error test fails.
- [ ] Remove fallback handling from `DeliveryPlannerAgent.run`.
- [ ] Run `uv run pytest tests/test_delivery_planner_agent.py -q` and confirm it passes.

### Task 2: Backend-Owned Plan Generation

- [ ] Update `tests/test_delivery_plan_service.py` so `generate_plan` receives no caller-supplied `planner_output` and instead invokes an injected planner.
- [ ] Update `tests/test_delivery_api.py` so `POST /meetings/{meeting_id}/delivery-plan` sends only `project_id`.
- [ ] Run targeted service/API tests and confirm failures identify the old request shape.
- [ ] Add a planner protocol/dependency to `DeliveryPlanService`.
- [ ] Build planner context from completed meeting, linked requirement, design docs, and sessions.
- [ ] Convert planner payloads to the existing raw task/gate structure internally.
- [ ] Run targeted service/API tests and confirm they pass.

### Task 3: Decision Gate Blocking And Versioning

- [ ] Add or update service tests so plans with decision gates create `preview` tasks and cannot start before resolution.
- [ ] Add or update service tests so resolving the gate stamps every actionable task with `decision_resolution_version`.
- [ ] Add or update service tests so missing/stale task decision versions block start.
- [ ] Run the new tests and confirm they fail against the current behavior.
- [ ] Change task creation, gate resolution, and start validation to enforce the tests.
- [ ] Run `uv run pytest tests/test_delivery_plan_service.py -q` and confirm it passes.

### Task 4: Server-Side Project Session Lookup

- [ ] Update service/API tests so start task does not accept a frontend `session_id`.
- [ ] Add a service/API test for missing `project_id + owner_agent` session.
- [ ] Run targeted tests and confirm they fail against the current request shape.
- [ ] Change `DeliveryPlanService.start_task` to look up the stored project agent session and use its `session_id`.
- [ ] Change `StartTaskRequest` to an empty body or remove it from the route.
- [ ] Run targeted service/API tests and confirm they pass.

### Task 5: Frontend Request Shape

- [ ] Update `web/src/lib/api.ts` so `deliveryApi.generatePlan` sends only `project_id` and `deliveryApi.startTask` sends no session id.
- [ ] Update `web/src/pages/DeliveryBoard.tsx` so task start calls the new client method without `session-placeholder`.
- [ ] Run `rg "session-placeholder|planner_output" web/src studio tests` and confirm no live caller still depends on those old shapes.
- [ ] Run frontend build.

### Task 6: Final Verification And Commit

- [ ] Run targeted backend tests:
  `uv run pytest tests/test_delivery_schemas.py tests/test_session_lease.py tests/test_delivery_plan_service.py tests/test_delivery_api.py tests/test_delivery_planner_agent.py tests/test_agent_profiles.py tests/test_claude_roles.py -q`
- [ ] Run frontend build.
- [ ] Review `git diff`.
- [ ] Commit the implementation changes on `feature/meeting-to-delivery-board`.

