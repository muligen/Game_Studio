# Delivery Acceptance Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated Delivery acceptance gate that verifies every requirement acceptance criterion with evidence, opens generated web games through Playwright, creates bug-fix tasks on failure, and marks requirements done only after acceptance passes.

**Architecture:** Add acceptance schemas and repositories, build an immutable contract from requirement and Delivery context, run command and Playwright validation inside the target project directory, evaluate criteria, then integrate the result into the Delivery LangGraph with a bounded bug loop. The board API and frontend expose validation status, evidence summaries/paths, and repair attempts.

**Tech Stack:** Python, Pydantic, LangGraph, FastAPI, StudioWorkspace JSON repositories, Playwright for Python, existing Delivery task runner, existing React Delivery board.

---

## Post-Merge Alignment

Merged commit `def68eb` implemented the core MVP from this plan. Treat the checklist below as the original implementation trail plus these current adjustments:

- Implemented: schemas/storage, contract builder, verifier, evaluator, Delivery graph gate, bug loop, acceptance run persistence, board API, board banner, and focused backend tests.
- Actual frontend files: `web/src/lib/api.ts`, `web/src/pages/DeliveryBoard.tsx`, and `web/src/components/board/DeliveryTaskCard.tsx`. The MVP did not create `web/src/api/client.ts`, `web/src/lib/types.ts`, or a standalone `AcceptanceGatePanel.tsx`.
- Actual API endpoints: `GET /api/delivery-plans/{plan_id}/acceptance-runs`, `GET /api/acceptance-runs/{run_id}`, and `POST /api/delivery-plans/{plan_id}/retry-acceptance`.
- Actual board payload: includes `acceptance_runs`; contracts are persisted in storage and referenced by run `contract_id`, but are not sent as `acceptance_contracts` yet.
- Remaining follow-ups: install command execution, artifact download endpoint, richer artifact browser, acceptance API tests, real browser E2E coverage, and dedicated Langfuse spans.

## File Structure

- Create `studio/schemas/acceptance.py`: Pydantic models for contracts, runs, criterion results, evidence, and artifact references.
- Create `studio/storage/acceptance_contract.py`: builder that merges requirement, meeting, gate, and task criteria.
- Create `studio/runtime/acceptance_verifier.py`: command detection, command execution, managed preview server startup, Playwright smoke checks, and evidence collection.
- Create `studio/runtime/acceptance_evaluator.py`: deterministic criterion evaluation and acceptance summary.
- Modify `studio/storage/workspace.py`: add repositories for acceptance contracts and acceptance runs.
- Modify `studio/schemas/delivery.py`: add plan statuses and task kind metadata.
- Modify `studio/storage/delivery_plan_service.py`: stop auto-completing requirements before acceptance, create bug-fix tasks, and persist acceptance events.
- Modify `studio/runtime/graph.py`: add `acceptance_gate` and bug loop transitions after task execution.
- Modify `studio/api/routes/delivery.py`: expose acceptance run list, single run details, and manual acceptance retry.
- Modify `web/src/lib/api.ts`: add acceptance board types and acceptance API calls.
- Modify `web/src/pages/DeliveryBoard.tsx` and board components: show Acceptance Gate status, criteria, evidence summaries/paths, and bug loop attempts.
- Add tests in `tests/test_acceptance_schemas.py`, `tests/test_acceptance_contract.py`, `tests/test_acceptance_verifier.py`, `tests/test_acceptance_evaluator.py`, `tests/test_delivery_acceptance_graph.py`, `tests/test_delivery_api.py`, and Delivery E2E tests.

## Task 1: Add Acceptance Schemas And Workspace Storage

**Files:**
- Create: `studio/schemas/acceptance.py`
- Modify: `studio/storage/workspace.py`
- Test: `tests/test_acceptance_schemas.py`

- [ ] **Step 1: Write schema persistence tests**

Create `tests/test_acceptance_schemas.py`:

```python
from __future__ import annotations

from studio.schemas.acceptance import (
    AcceptanceContract,
    AcceptanceCriterion,
    AcceptanceCriterionResult,
    AcceptanceEvidence,
    AcceptanceRun,
)
from studio.storage.workspace import StudioWorkspace


def test_acceptance_contract_and_run_persist(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()

    contract = AcceptanceContract(
        id="contract_plan_001",
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        criteria=[
            AcceptanceCriterion(
                id="crit_startup",
                source="system",
                text="The game opens without fatal browser errors.",
                required_evidence_types=["playwright"],
                severity="blocker",
                owner_hint="dev",
            )
        ],
    )
    saved_contract = ws.acceptance_contracts.save(contract)

    evidence = AcceptanceEvidence(
        id="ev_console",
        evidence_type="console",
        summary="No fatal console errors were observed.",
        artifact_path="acceptance/run_001/console.json",
    )
    run = AcceptanceRun(
        id="acc_run_001",
        contract_id=saved_contract.id,
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        attempt_number=1,
        status="passed",
        evidence=[evidence],
        criteria_results=[
            AcceptanceCriterionResult(
                criterion_id="crit_startup",
                status="passed",
                evidence_ids=["ev_console"],
                reason="Playwright opened the page and no fatal errors were captured.",
                blocking=True,
            )
        ],
    )
    ws.acceptance_runs.save(run)

    assert ws.acceptance_contracts.get("contract_plan_001").criteria[0].severity == "blocker"
    assert ws.acceptance_runs.get("acc_run_001").criteria_results[0].status == "passed"
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
uv run pytest tests/test_acceptance_schemas.py -q
```

Expected: fail because `studio.schemas.acceptance` and workspace repositories do not exist.

- [ ] **Step 3: Add acceptance schema models**

Create `studio/schemas/acceptance.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from studio.schemas.artifact import StrippedNonEmptyStr


AcceptanceSeverity = Literal["blocker", "major", "minor"]
AcceptanceEvidenceType = Literal["command", "playwright", "console", "pageerror", "screenshot", "video", "file", "llm"]
AcceptanceCriterionStatus = Literal["passed", "failed", "inconclusive"]
AcceptanceRunStatus = Literal["running", "passed", "failed", "needs_attention"]
AcceptanceOwnerHint = Literal["dev", "art", "qa", "reviewer", "quality"]


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    source: StrippedNonEmptyStr
    text: StrippedNonEmptyStr
    required_evidence_types: list[AcceptanceEvidenceType] = Field(default_factory=list)
    severity: AcceptanceSeverity = "major"
    owner_hint: AcceptanceOwnerHint = "qa"


class AcceptanceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    criteria: list[AcceptanceCriterion]
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class AcceptanceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    evidence_type: AcceptanceEvidenceType
    summary: StrippedNonEmptyStr
    artifact_path: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class AcceptanceCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: StrippedNonEmptyStr
    status: AcceptanceCriterionStatus
    evidence_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    reason: StrippedNonEmptyStr
    repair_hint: str | None = None
    owner_hint: AcceptanceOwnerHint = "qa"
    blocking: bool = True


class AcceptanceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrippedNonEmptyStr
    contract_id: StrippedNonEmptyStr
    plan_id: StrippedNonEmptyStr
    requirement_id: StrippedNonEmptyStr
    project_id: StrippedNonEmptyStr
    attempt_number: int = 1
    status: AcceptanceRunStatus = "running"
    evidence: list[AcceptanceEvidence] = Field(default_factory=list)
    criteria_results: list[AcceptanceCriterionResult] = Field(default_factory=list)
    repair_task_ids: list[StrippedNonEmptyStr] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
```

- [ ] **Step 4: Add repositories to workspace**

Modify `studio/storage/workspace.py`:

```python
from studio.schemas.acceptance import AcceptanceContract, AcceptanceRun
```

Inside `StudioWorkspace.__init__`, add:

```python
self.acceptance_contracts = JsonRepository(root / "acceptance_contracts", AcceptanceContract)
self.acceptance_runs = JsonRepository(root / "acceptance_runs", AcceptanceRun)
```

Inside `ensure_layout()`, include:

```python
self.acceptance_contracts.root,
self.acceptance_runs.root,
```

- [ ] **Step 5: Run the schema test**

Run:

```powershell
uv run pytest tests/test_acceptance_schemas.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add studio/schemas/acceptance.py studio/storage/workspace.py tests/test_acceptance_schemas.py
git commit -m "feat: add acceptance gate storage models"
```

## Task 2: Build Acceptance Contracts From Requirement And Delivery Context

**Files:**
- Create: `studio/storage/acceptance_contract.py`
- Test: `tests/test_acceptance_contract.py`

- [ ] **Step 1: Write contract builder tests**

Create `tests/test_acceptance_contract.py`:

```python
from __future__ import annotations

from studio.schemas.delivery import DeliveryPlan, DeliveryTask, GateItem, KickoffDecisionGate
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.storage.acceptance_contract import build_acceptance_contract
from studio.storage.workspace import StudioWorkspace


def test_contract_merges_sources_and_adds_startup_criteria(tmp_path):
    ws = StudioWorkspace(tmp_path)
    ws.ensure_layout()
    ws.requirements.save(
        RequirementCard(
            id="req_001",
            title="Snake MVP",
            status="implementing",
            acceptance_criteria=["Arrow keys move the snake"],
        )
    )
    ws.meetings.save(
        MeetingMinutes(
            id="meet_001",
            requirement_id="req_001",
            title="Kickoff",
            status="completed",
            decisions=["Use retro pixel style"],
            consensus_points=["Browser game delivery"],
        )
    )
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="active",
            task_ids=["task_001"],
            decision_gate_id="gate_001",
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
            items=[
                GateItem(
                    id="style",
                    question="Choose style",
                    context="Visual direction",
                    options=["retro pixel", "minimal"],
                    resolution="retro pixel",
                )
            ],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement controls",
            description="Move with arrows",
            owner_agent="dev",
            status="done",
            acceptance_criteria=["Controls respond under 100ms"],
        )
    )

    contract = build_acceptance_contract(ws, "plan_001")
    texts = [criterion.text for criterion in contract.criteria]

    assert "Arrow keys move the snake" in texts
    assert "Kickoff decision resolved: Choose style -> retro pixel" in texts
    assert "Controls respond under 100ms" in texts
    assert "The project exposes a detectable command to start or preview the game." in texts
    assert "The browser page opens without fatal page errors." in texts
    assert len(texts) == len(set(texts))
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
uv run pytest tests/test_acceptance_contract.py -q
```

Expected: fail because the contract builder does not exist.

- [ ] **Step 3: Implement contract builder**

Create `studio/storage/acceptance_contract.py`:

```python
from __future__ import annotations

import re

from studio.schemas.acceptance import AcceptanceContract, AcceptanceCriterion
from studio.storage.workspace import StudioWorkspace


_SYSTEM_CRITERIA: list[tuple[str, list[str], str]] = [
    ("The project exposes a detectable command to start or preview the game.", ["command"], "dev"),
    ("The project builds successfully when a build command exists.", ["command"], "dev"),
    ("The project tests pass when a test command exists.", ["command"], "qa"),
    ("The browser page opens without fatal page errors.", ["playwright", "pageerror"], "dev"),
    ("The browser console has no fatal runtime errors.", ["console"], "dev"),
    ("The page renders a visible game surface and is not blank.", ["playwright", "screenshot"], "qa"),
]


def build_acceptance_contract(ws: StudioWorkspace, plan_id: str) -> AcceptanceContract:
    plan = ws.delivery_plans.get(plan_id)
    requirement = ws.requirements.get(plan.requirement_id)
    meeting = ws.meetings.get(plan.meeting_id)
    raw_items: list[tuple[str, str, list[str], str, str]] = []

    for criterion in requirement.acceptance_criteria:
        raw_items.append(("requirement", str(criterion), ["llm"], "major", "qa"))

    for decision in meeting.decisions:
        raw_items.append(("meeting_decision", str(decision), ["llm"], "major", "qa"))

    for consensus in meeting.consensus_points:
        raw_items.append(("meeting_consensus", str(consensus), ["llm"], "minor", "qa"))

    if plan.decision_gate_id:
        gate = ws.decision_gates.get(plan.decision_gate_id)
        for item in gate.items:
            if item.resolution:
                raw_items.append(
                    (
                        "kickoff_decision",
                        f"Kickoff decision resolved: {item.question} -> {item.resolution}",
                        ["llm"],
                        "major",
                        "qa",
                    )
                )

    for task_id in plan.task_ids:
        task = ws.delivery_tasks.get(task_id)
        for criterion in task.acceptance_criteria:
            raw_items.append((f"task:{task.id}", str(criterion), ["llm"], "major", str(task.owner_agent)))

    for text, evidence_types, owner_hint in _SYSTEM_CRITERIA:
        raw_items.append(("system", text, evidence_types, "blocker", owner_hint))

    seen: set[str] = set()
    criteria: list[AcceptanceCriterion] = []
    for source, text, evidence_types, severity, owner_hint in raw_items:
        normalized = " ".join(text.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        criteria.append(
            AcceptanceCriterion(
                id=f"crit_{len(criteria) + 1:03d}_{_slug(normalized)}",
                source=source,
                text=normalized,
                required_evidence_types=evidence_types,
                severity=severity,
                owner_hint=_owner_hint(owner_hint),
            )
        )

    return AcceptanceContract(
        id=f"contract_{plan.id}",
        plan_id=plan.id,
        requirement_id=plan.requirement_id,
        project_id=plan.project_id,
        criteria=criteria,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug[:40] or "criterion"


def _owner_hint(value: str) -> str:
    return value if value in {"dev", "art", "qa", "reviewer", "quality"} else "qa"
```

- [ ] **Step 4: Run contract tests**

Run:

```powershell
uv run pytest tests/test_acceptance_contract.py tests/test_acceptance_schemas.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add studio/storage/acceptance_contract.py tests/test_acceptance_contract.py
git commit -m "feat: build delivery acceptance contracts"
```

## Task 3: Add Project Command And Playwright Verification

**Files:**
- Create: `studio/runtime/acceptance_verifier.py`
- Test: `tests/test_acceptance_verifier.py`

- [ ] **Step 1: Write command detection and failure tests**

Create `tests/test_acceptance_verifier.py`:

```python
from __future__ import annotations

import json

from studio.runtime.acceptance_verifier import detect_node_commands, verify_project


def test_detect_node_commands_prefers_npm_ci_for_package_lock(tmp_path):
    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    (project_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (project_dir / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build", "test": "vitest run", "preview": "vite preview"}}),
        encoding="utf-8",
    )

    commands = detect_node_commands(project_dir)

    assert commands.install == ["npm", "ci"]
    assert commands.build == ["npm", "run", "build"]
    assert commands.test == ["npm", "run", "test"]
    assert commands.preview == ["npm", "run", "preview"]


def test_verify_project_fails_when_package_json_missing(tmp_path):
    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_001")

    assert result.startup_ok is False
    assert any("package.json" in error for error in result.errors)
    assert result.evidence
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/test_acceptance_verifier.py -q
```

Expected: fail because verifier module does not exist.

- [ ] **Step 3: Implement command detection and non-browser failure path**

Create `studio/runtime/acceptance_verifier.py` with command models and the initial failure path:

```python
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from studio.schemas.acceptance import AcceptanceEvidence


@dataclass(frozen=True)
class NodeCommands:
    install: list[str] | None
    build: list[str] | None
    test: list[str] | None
    preview: list[str] | None


@dataclass
class VerificationResult:
    startup_ok: bool
    build_ok: bool | None = None
    test_ok: bool | None = None
    browser_ok: bool | None = None
    evidence: list[AcceptanceEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def detect_node_commands(project_dir: Path) -> NodeCommands:
    package_json = project_dir / "package.json"
    if not package_json.exists():
        return NodeCommands(install=None, build=None, test=None, preview=None)
    data = json.loads(package_json.read_text(encoding="utf-8"))
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    package_manager = _package_manager(project_dir)
    install = _install_command(project_dir, package_manager)
    build = [package_manager, "run", "build"] if "build" in scripts else None
    test = [package_manager, "run", "test"] if _has_real_test_script(scripts) else None
    preview_script = next((name for name in ("preview", "start", "dev") if name in scripts), None)
    preview = [package_manager, "run", preview_script] if preview_script else None
    return NodeCommands(install=install, build=build, test=test, preview=preview)


def verify_project(project_dir: Path, *, artifacts_root: Path, run_id: str) -> VerificationResult:
    artifacts_dir = artifacts_root / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if not (project_dir / "package.json").exists():
        evidence = AcceptanceEvidence(
            id="ev_package_missing",
            evidence_type="file",
            summary="package.json was not found in the target project directory.",
            artifact_path=None,
        )
        return VerificationResult(
            startup_ok=False,
            browser_ok=False,
            evidence=[evidence],
            errors=["package.json missing from project_dir"],
        )

    commands = detect_node_commands(project_dir)
    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    build_ok = _run_optional_command(project_dir, artifacts_dir, "build", commands.build, evidence, errors)
    test_ok = _run_optional_command(project_dir, artifacts_dir, "test", commands.test, evidence, errors)
    if commands.preview is None:
        evidence.append(
            AcceptanceEvidence(
                id="ev_preview_missing",
                evidence_type="command",
                summary="No preview, start, or dev script was found.",
            )
        )
        errors.append("preview command missing")
        return VerificationResult(
            startup_ok=False,
            build_ok=build_ok,
            test_ok=test_ok,
            browser_ok=False,
            evidence=evidence,
            errors=errors,
        )
    evidence.append(
        AcceptanceEvidence(
            id="ev_preview_detected",
            evidence_type="command",
            summary=f"Preview command detected: {' '.join(commands.preview)}",
        )
    )
    return VerificationResult(
        startup_ok=not errors,
        build_ok=build_ok,
        test_ok=test_ok,
        browser_ok=None,
        evidence=evidence,
        errors=errors,
    )
```

Add helper functions below it:

```python
def _package_manager(project_dir: Path) -> str:
    if (project_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_dir / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _install_command(project_dir: Path, package_manager: str) -> list[str] | None:
    if package_manager == "pnpm":
        return ["pnpm", "install", "--frozen-lockfile"]
    if package_manager == "yarn":
        return ["yarn", "install", "--frozen-lockfile"]
    if (project_dir / "package-lock.json").exists():
        return ["npm", "ci"]
    return ["npm", "install"]


def _has_real_test_script(scripts: object) -> bool:
    if not isinstance(scripts, dict) or "test" not in scripts:
        return False
    script = str(scripts["test"]).strip().lower()
    placeholder_parts = ["no test specified", "exit 1"]
    return not all(part in script for part in placeholder_parts)


def _run_optional_command(
    project_dir: Path,
    artifacts_dir: Path,
    name: str,
    command: list[str] | None,
    evidence: list[AcceptanceEvidence],
    errors: list[str],
) -> bool | None:
    if command is None:
        evidence.append(
            AcceptanceEvidence(
                id=f"ev_{name}_absent",
                evidence_type="command",
                summary=f"No {name} command was defined.",
            )
        )
        return None
    log_path = artifacts_dir / f"{name}.log"
    completed = subprocess.run(
        command,
        cwd=project_dir,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    log_path.write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    passed = completed.returncode == 0
    evidence.append(
        AcceptanceEvidence(
            id=f"ev_{name}",
            evidence_type="command",
            summary=f"{name} command exited with code {completed.returncode}.",
            artifact_path=str(log_path),
            metadata={"command": command, "returncode": completed.returncode},
        )
    )
    if not passed:
        errors.append(f"{name} command failed with exit code {completed.returncode}")
    return passed
```

- [ ] **Step 4: Add Playwright browser smoke test**

Extend `verify_project()` after preview command detection to start the server and call a new `_run_playwright_smoke()` helper. Add tests that monkeypatch `_run_playwright_smoke()` to avoid launching a real browser in unit tests:

```python
def test_verify_project_uses_browser_result(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    (project_dir / "package.json").write_text(
        json.dumps({"scripts": {"preview": "vite preview"}}),
        encoding="utf-8",
    )

    def fake_browser(*args, **kwargs):
        return True, [
            AcceptanceEvidence(
                id="ev_browser_opened",
                evidence_type="playwright",
                summary="Browser opened the page.",
            )
        ], []

    monkeypatch.setattr("studio.runtime.acceptance_verifier._run_playwright_smoke", fake_browser)

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_001")

    assert result.browser_ok is True
    assert result.startup_ok is True
```

Implement `_run_playwright_smoke()` with Playwright sync API:

```python
def _run_playwright_smoke(project_dir: Path, artifacts_dir: Path, preview_command: list[str]) -> tuple[bool, list[AcceptanceEvidence], list[str]]:
    from playwright.sync_api import sync_playwright

    port = _free_port()
    command = [*preview_command, "--", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(
        command,
        cwd=project_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    log_path = artifacts_dir / "preview.log"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(record_video_dir=str(artifacts_dir / "videos"))
            page = context.new_page()
            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
            screenshot_path = artifacts_dir / "startup.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            visible_surface = page.locator("canvas, #root, main, [data-game-root]").count() > 0
            context.close()
            browser.close()
            if page_errors:
                errors.extend(f"pageerror: {item}" for item in page_errors)
            fatal_console = [item for item in console_errors if _is_fatal_console_error(item)]
            if fatal_console:
                errors.extend(f"console: {item}" for item in fatal_console)
            if not visible_surface:
                errors.append("no visible game surface found")
            evidence.append(
                AcceptanceEvidence(
                    id="ev_playwright_startup",
                    evidence_type="playwright",
                    summary="Playwright opened the game page and captured startup state.",
                    artifact_path=str(screenshot_path),
                    metadata={"console_errors": console_errors, "page_errors": page_errors, "visible_surface": visible_surface},
                )
            )
    finally:
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=5)
        log_path.write_text(stdout or "", encoding="utf-8")
    return not errors, evidence, errors
```

Add `_free_port()` and `_is_fatal_console_error()` helpers:

```python
def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_fatal_console_error(message: str) -> bool:
    lowered = message.lower()
    fatal_markers = ["uncaught", "syntaxerror", "referenceerror", "typeerror", "failed to fetch dynamically imported module"]
    return any(marker in lowered for marker in fatal_markers)
```

- [ ] **Step 5: Run verifier tests**

Run:

```powershell
uv run pytest tests/test_acceptance_verifier.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add studio/runtime/acceptance_verifier.py tests/test_acceptance_verifier.py
git commit -m "feat: add delivery project acceptance verifier"
```

## Task 4: Evaluate Criteria And Block Fallback Success

**Files:**
- Create: `studio/runtime/acceptance_evaluator.py`
- Test: `tests/test_acceptance_evaluator.py`

- [ ] **Step 1: Write evaluator tests**

Create `tests/test_acceptance_evaluator.py`:

```python
from __future__ import annotations

from studio.runtime.acceptance_evaluator import evaluate_acceptance
from studio.runtime.acceptance_verifier import VerificationResult
from studio.schemas.acceptance import AcceptanceContract, AcceptanceCriterion, AcceptanceEvidence


def _contract():
    return AcceptanceContract(
        id="contract_plan_001",
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        criteria=[
            AcceptanceCriterion(
                id="crit_start",
                source="system",
                text="The browser page opens without fatal page errors.",
                required_evidence_types=["playwright"],
                severity="blocker",
                owner_hint="dev",
            ),
            AcceptanceCriterion(
                id="crit_controls",
                source="requirement",
                text="Arrow keys move the snake",
                required_evidence_types=["llm"],
                severity="major",
                owner_hint="qa",
            ),
        ],
    )


def test_startup_failure_blocks_acceptance():
    run = evaluate_acceptance(
        contract=_contract(),
        verification=VerificationResult(startup_ok=False, browser_ok=False, errors=["pageerror: boom"]),
        task_results=[],
        run_id="acc_run_001",
        attempt_number=1,
    )

    assert run.status == "failed"
    failed = {result.criterion_id: result for result in run.criteria_results if result.status == "failed"}
    assert "crit_start" in failed
    assert failed["crit_start"].blocking is True


def test_criterion_cannot_pass_without_evidence():
    run = evaluate_acceptance(
        contract=_contract(),
        verification=VerificationResult(startup_ok=True, browser_ok=True, evidence=[]),
        task_results=[],
        run_id="acc_run_001",
        attempt_number=1,
    )

    assert run.status == "failed"
    assert any(result.status != "passed" for result in run.criteria_results)


def test_playwright_evidence_passes_startup_criterion():
    evidence = AcceptanceEvidence(
        id="ev_playwright_startup",
        evidence_type="playwright",
        summary="Playwright opened the page.",
    )
    run = evaluate_acceptance(
        contract=_contract(),
        verification=VerificationResult(startup_ok=True, browser_ok=True, evidence=[evidence]),
        task_results=[{"context_warnings": [], "tests_or_checks": ["manual check: controls verified"]}],
        run_id="acc_run_001",
        attempt_number=1,
    )

    start_result = next(result for result in run.criteria_results if result.criterion_id == "crit_start")
    assert start_result.status == "passed"
    assert start_result.evidence_ids == ["ev_playwright_startup"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/test_acceptance_evaluator.py -q
```

Expected: fail because evaluator module does not exist.

- [ ] **Step 3: Implement deterministic evaluator**

Create `studio/runtime/acceptance_evaluator.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from studio.runtime.acceptance_verifier import VerificationResult
from studio.schemas.acceptance import AcceptanceContract, AcceptanceCriterion, AcceptanceCriterionResult, AcceptanceRun


def evaluate_acceptance(
    *,
    contract: AcceptanceContract,
    verification: VerificationResult,
    task_results: list[dict[str, object]],
    run_id: str,
    attempt_number: int,
) -> AcceptanceRun:
    results = [
        _evaluate_criterion(criterion, verification, task_results)
        for criterion in contract.criteria
    ]
    blocking_failures = [
        result for result in results
        if result.blocking and result.status != "passed"
    ]
    return AcceptanceRun(
        id=run_id,
        contract_id=contract.id,
        plan_id=contract.plan_id,
        requirement_id=contract.requirement_id,
        project_id=contract.project_id,
        attempt_number=attempt_number,
        status="passed" if not blocking_failures else "failed",
        evidence=verification.evidence,
        criteria_results=results,
        completed_at=datetime.now(UTC).isoformat(),
    )


def _evaluate_criterion(
    criterion: AcceptanceCriterion,
    verification: VerificationResult,
    task_results: list[dict[str, object]],
) -> AcceptanceCriterionResult:
    blocking = criterion.severity in {"blocker", "major"}
    matching_evidence = [
        evidence for evidence in verification.evidence
        if evidence.evidence_type in criterion.required_evidence_types
    ]
    text = criterion.text.lower()
    if criterion.source == "system":
        return _evaluate_system_criterion(criterion, verification, matching_evidence, blocking)
    if _has_fallback_warning(task_results):
        return AcceptanceCriterionResult(
            criterion_id=criterion.id,
            status="failed",
            evidence_ids=[],
            reason="Agent fallback output was present, so requirement criteria need repair or real validation evidence.",
            repair_hint=f"Produce real evidence for: {criterion.text}",
            owner_hint=criterion.owner_hint,
            blocking=blocking,
        )
    if matching_evidence:
        return AcceptanceCriterionResult(
            criterion_id=criterion.id,
            status="passed",
            evidence_ids=[evidence.id for evidence in matching_evidence],
            reason="Criterion has matching validation evidence.",
            owner_hint=criterion.owner_hint,
            blocking=blocking,
        )
    if any(str(check).strip() for result in task_results for check in result.get("tests_or_checks", [])):
        return AcceptanceCriterionResult(
            criterion_id=criterion.id,
            status="passed",
            evidence_ids=[],
            reason="Task check output exists for this requirement-level criterion.",
            owner_hint=criterion.owner_hint,
            blocking=blocking,
        )
    return AcceptanceCriterionResult(
        criterion_id=criterion.id,
        status="failed" if blocking else "inconclusive",
        evidence_ids=[],
        reason="No evidence was recorded for this acceptance criterion.",
        repair_hint=f"Add validation evidence for: {criterion.text}",
        owner_hint=criterion.owner_hint,
        blocking=blocking,
    )
```

Add helper functions:

```python
def _evaluate_system_criterion(
    criterion: AcceptanceCriterion,
    verification: VerificationResult,
    matching_evidence,
    blocking: bool,
) -> AcceptanceCriterionResult:
    text = criterion.text.lower()
    if "browser page opens" in text and not verification.browser_ok:
        return _failed(criterion, "Playwright could not prove that the browser page opens cleanly.", blocking)
    if "console" in text and verification.errors:
        return _failed(criterion, "; ".join(verification.errors), blocking)
    if "builds successfully" in text and verification.build_ok is False:
        return _failed(criterion, "Build command failed.", blocking)
    if "tests pass" in text and verification.test_ok is False:
        return _failed(criterion, "Test command failed.", blocking)
    if "detectable command" in text and not verification.startup_ok:
        return _failed(criterion, "No working start or preview path was detected.", blocking)
    if matching_evidence:
        return AcceptanceCriterionResult(
            criterion_id=criterion.id,
            status="passed",
            evidence_ids=[evidence.id for evidence in matching_evidence],
            reason="System validation produced matching evidence.",
            owner_hint=criterion.owner_hint,
            blocking=blocking,
        )
    return _failed(criterion, "System criterion has no matching evidence.", blocking)


def _failed(criterion: AcceptanceCriterion, reason: str, blocking: bool) -> AcceptanceCriterionResult:
    return AcceptanceCriterionResult(
        criterion_id=criterion.id,
        status="failed",
        evidence_ids=[],
        reason=reason,
        repair_hint=f"Fix validation failure for: {criterion.text}",
        owner_hint=criterion.owner_hint,
        blocking=blocking,
    )


def _has_fallback_warning(task_results: list[dict[str, object]]) -> bool:
    for result in task_results:
        warnings = result.get("context_warnings", [])
        if isinstance(warnings, list) and any("fallback" in str(item).lower() for item in warnings):
            return True
    return False
```

- [ ] **Step 4: Run evaluator tests**

Run:

```powershell
uv run pytest tests/test_acceptance_evaluator.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add studio/runtime/acceptance_evaluator.py tests/test_acceptance_evaluator.py
git commit -m "feat: evaluate delivery acceptance criteria"
```

## Task 5: Integrate Acceptance Gate Into Delivery Graph

**Files:**
- Modify: `studio/schemas/delivery.py`
- Modify: `studio/storage/delivery_plan_service.py`
- Modify: `studio/runtime/graph.py`
- Test: `tests/test_delivery_acceptance_graph.py`

- [ ] **Step 1: Write graph tests for accepted and failed gates**

Create `tests/test_delivery_acceptance_graph.py`:

```python
from __future__ import annotations

from pathlib import Path

from studio.schemas.acceptance import AcceptanceEvidence
from studio.schemas.delivery import DeliveryPlan, DeliveryTask
from studio.schemas.meeting import MeetingMinutes
from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def _seed_done_plan(workspace_root: Path) -> str:
    ws = StudioWorkspace(workspace_root)
    ws.ensure_layout()
    ws.requirements.save(
        RequirementCard(
            id="req_001",
            title="Snake MVP",
            status="implementing",
            acceptance_criteria=["Game opens"],
        )
    )
    ws.meetings.save(MeetingMinutes(id="meet_001", requirement_id="req_001", title="Kickoff", status="completed"))
    ws.delivery_plans.save(
        DeliveryPlan(
            id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            status="active",
            task_ids=["task_001"],
        )
    )
    ws.delivery_tasks.save(
        DeliveryTask(
            id="task_001",
            plan_id="plan_001",
            meeting_id="meet_001",
            requirement_id="req_001",
            project_id="proj_001",
            title="Implement game",
            description="Create playable game",
            owner_agent="dev",
            status="done",
            execution_result_id="result_task_001",
        )
    )
    return "plan_001"


def test_delivery_graph_marks_requirement_done_only_after_acceptance_passes(tmp_path, monkeypatch):
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_done_plan(workspace_root)

    def fake_verify(project_dir, *, artifacts_root, run_id):
        from studio.runtime.acceptance_verifier import VerificationResult

        return VerificationResult(
            startup_ok=True,
            browser_ok=True,
            evidence=[
                AcceptanceEvidence(
                    id="ev_playwright_startup",
                    evidence_type="playwright",
                    summary="Browser opened.",
                )
            ],
        )

    monkeypatch.setattr("studio.runtime.graph.verify_project", fake_verify)

    result = build_delivery_graph().invoke(
        {"workspace_root": str(workspace_root), "project_root": str(project_root), "plan_id": plan_id}
    )

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "accepted"
    assert ws.delivery_plans.get(plan_id).status == "accepted"
    assert ws.requirements.get("req_001").status == "done"


def test_delivery_graph_creates_bug_task_when_acceptance_fails(tmp_path, monkeypatch):
    from studio.runtime.graph import build_delivery_graph

    workspace_root = tmp_path / ".studio-data"
    project_root = tmp_path
    plan_id = _seed_done_plan(workspace_root)

    def fake_verify(project_dir, *, artifacts_root, run_id):
        from studio.runtime.acceptance_verifier import VerificationResult

        return VerificationResult(startup_ok=False, browser_ok=False, errors=["pageerror: boom"])

    monkeypatch.setattr("studio.runtime.graph.verify_project", fake_verify)

    result = build_delivery_graph().invoke(
        {"workspace_root": str(workspace_root), "project_root": str(project_root), "plan_id": plan_id}
    )

    ws = StudioWorkspace(workspace_root)
    assert result["runner_status"] == "repairing"
    bug_tasks = [task for task in ws.delivery_tasks.list_all() if getattr(task, "task_kind", "delivery") == "bug_fix"]
    assert len(bug_tasks) == 1
    assert ws.requirements.get("req_001").status != "done"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/test_delivery_acceptance_graph.py -q
```

Expected: fail because statuses, task kind, and graph gate are not implemented.

- [ ] **Step 3: Add delivery statuses and task kind**

Modify `studio/schemas/delivery.py`:

```python
DeliveryPlanStatus = Literal[
    "awaiting_user_decision",
    "active",
    "validating",
    "repairing",
    "accepted",
    "completed",
    "needs_attention",
    "cancelled",
]

DeliveryTaskKind = Literal["delivery", "bug_fix", "acceptance"]
```

Add to `DeliveryTask`:

```python
task_kind: DeliveryTaskKind = "delivery"
```

- [ ] **Step 4: Stop auto-completing requirement from `complete_task()`**

In `DeliveryPlanService.complete_task()`, replace the current all-tasks-done block with:

```python
if all(candidate.status == "done" for candidate in refreshed_tasks):
    plan = plan.model_copy(update={"status": "validating", "updated_at": now})
    self._ws.delivery_plans.save(plan)
```

Do not transition the requirement to `done` in this method.

- [ ] **Step 5: Add service helpers for acceptance pass and bug task creation**

Add methods to `DeliveryPlanService`:

```python
def mark_plan_accepted(self, plan_id: str) -> None:
    plan = self._ws.delivery_plans.get(plan_id)
    now = datetime.now(UTC).isoformat()
    self._ws.delivery_plans.save(plan.model_copy(update={"status": "accepted", "updated_at": now}))
    req = self._ws.requirements.get(plan.requirement_id)
    if req.status != "done":
        req = transition_requirement(req, "done")
        self._ws.requirements.save(req)


def create_acceptance_bug_tasks(self, plan_id: str, failed_results: list[object], attempt_number: int) -> list[DeliveryTask]:
    plan = self._ws.delivery_plans.get(plan_id)
    now = datetime.now(UTC).isoformat()
    created: list[DeliveryTask] = []
    for index, result in enumerate(failed_results, start=1):
        owner = getattr(result, "owner_hint", "dev")
        if owner not in VALID_OWNER_AGENTS:
            owner = "dev"
        task = DeliveryTask(
            id=f"task_bug_{uuid4().hex}",
            plan_id=plan.id,
            meeting_id=plan.meeting_id,
            requirement_id=plan.requirement_id,
            project_id=plan.project_id,
            title=f"Fix acceptance failure {attempt_number}.{index}",
            description=f"{getattr(result, 'reason', '')}\n\nRepair hint: {getattr(result, 'repair_hint', '')}",
            owner_agent=owner,
            status="ready",
            task_kind="bug_fix",
            depends_on_task_ids=[],
            acceptance_criteria=[str(getattr(result, "repair_hint", getattr(result, "reason", "")))],
            decision_resolution_version=plan.decision_resolution_version,
            updated_at=now,
        )
        self._ws.delivery_tasks.save(task)
        created.append(task)
    self._ws.delivery_plans.save(
        plan.model_copy(update={"status": "repairing", "task_ids": [*plan.task_ids, *[task.id for task in created]], "updated_at": now})
    )
    return created
```

- [ ] **Step 6: Add acceptance gate node to graph**

In `studio/runtime/graph.py`, import inside `build_delivery_graph()`:

```python
from studio.runtime.acceptance_evaluator import evaluate_acceptance
from studio.runtime.acceptance_verifier import verify_project
from studio.storage.acceptance_contract import build_acceptance_contract
```

Add an `acceptance_gate_node` after `run_delivery_node`:

```python
def acceptance_gate_node(state: _DeliveryState) -> dict[str, object]:
    if state.get("runner_status") not in {"completed", "running"}:
        return dict(state)
    workspace_root = Path(_require_state_str(state, "workspace_root"))
    project_root = Path(_require_state_str(state, "project_root"))
    plan_id = _require_state_str(state, "plan_id")
    service = DeliveryPlanService(workspace_root, project_root=project_root)
    ws = service._ws
    plan = ws.delivery_plans.get(plan_id)
    tasks = [ws.delivery_tasks.get(task_id) for task_id in plan.task_ids]
    if any(task.status != "done" for task in tasks):
        return dict(state)
    existing_runs = [run for run in ws.acceptance_runs.list_all() if run.plan_id == plan_id]
    attempt_number = len(existing_runs) + 1
    contract = build_acceptance_contract(ws, plan_id)
    ws.acceptance_contracts.save(contract)
    tracker = GitTracker(repo_root=project_root, project_id=plan.project_id)
    project_dir = tracker.ensure_project_dir()
    run_id = f"acc_{plan_id}_{attempt_number}"
    verification = verify_project(project_dir, artifacts_root=workspace_root / "artifacts", run_id=run_id)
    task_results = [
        ws.execution_results.get(task.execution_result_id).model_dump(mode="json")
        for task in tasks
        if task.execution_result_id
    ]
    acceptance_run = evaluate_acceptance(
        contract=contract,
        verification=verification,
        task_results=task_results,
        run_id=run_id,
        attempt_number=attempt_number,
    )
    ws.acceptance_runs.save(acceptance_run)
    if acceptance_run.status == "passed":
        service.mark_plan_accepted(plan_id)
        return {**state, "runner_status": "accepted"}
    max_attempts = int(os.environ.get("GAME_STUDIO_ACCEPTANCE_MAX_ATTEMPTS", "3"))
    failed_blockers = [
        result for result in acceptance_run.criteria_results
        if result.blocking and result.status != "passed"
    ]
    if attempt_number >= max_attempts:
        ws.delivery_plans.save(plan.model_copy(update={"status": "needs_attention"}))
        return {**state, "runner_status": "needs_attention", "failed_task_ids": [result.criterion_id for result in failed_blockers]}
    bug_tasks = service.create_acceptance_bug_tasks(plan_id, failed_blockers, attempt_number)
    acceptance_run = acceptance_run.model_copy(update={"repair_task_ids": [task.id for task in bug_tasks]})
    ws.acceptance_runs.save(acceptance_run)
    return {**state, "runner_status": "repairing", "failed_task_ids": [task.id for task in bug_tasks]}
```

Add `import os` near the top of `graph.py`.

Update graph edges:

```python
graph.add_node("acceptance_gate", acceptance_gate_node)
graph.add_edge("run_task", "acceptance_gate")
graph.add_edge("acceptance_gate", "finalize_delivery")
```

Remove the direct `run_task -> finalize_delivery` edge.

- [ ] **Step 7: Run graph tests**

Run:

```powershell
uv run pytest tests/test_delivery_acceptance_graph.py tests/test_delivery_graph.py -q
```

Expected: pass after adjusting older tests that expected `completed`; new success status is `accepted`.

- [ ] **Step 8: Commit**

```powershell
git add studio/schemas/delivery.py studio/storage/delivery_plan_service.py studio/runtime/graph.py tests/test_delivery_acceptance_graph.py tests/test_delivery_graph.py
git commit -m "feat: gate delivery completion on acceptance"
```

## Task 6: Expose Acceptance State Through API

**Files:**
- Modify: `studio/api/routes/delivery.py`
- Test: `tests/test_delivery_api.py`

- [ ] **Step 1: Write API tests**

Add to `tests/test_delivery_api.py`:

```python
def test_delivery_board_includes_acceptance_runs(client, workspace):
    from studio.schemas.acceptance import AcceptanceContract, AcceptanceCriterion, AcceptanceRun
    from studio.storage.workspace import StudioWorkspace

    ws = StudioWorkspace(workspace / ".studio-data")
    ws.ensure_layout()
    ws.acceptance_contracts.save(
        AcceptanceContract(
            id="contract_plan_001",
            plan_id="plan_001",
            requirement_id="req_001",
            project_id="proj_001",
            criteria=[
                AcceptanceCriterion(
                    id="crit_start",
                    source="system",
                    text="The browser page opens without fatal page errors.",
                    required_evidence_types=["playwright"],
                    severity="blocker",
                    owner_hint="dev",
                )
            ],
        )
    )
    ws.acceptance_runs.save(
        AcceptanceRun(
            id="acc_run_001",
            contract_id="contract_plan_001",
            plan_id="plan_001",
            requirement_id="req_001",
            project_id="proj_001",
            attempt_number=1,
            status="failed",
        )
    )

    resp = client.get("/api/delivery-board", params={"workspace": str(workspace)})

    assert resp.status_code == 200
    data = resp.json()
    assert data["acceptance_runs"][0]["id"] == "acc_run_001"
    # Post-merge MVP note: contracts are persisted but not included in board payload yet.
```

- [ ] **Step 2: Run API test and verify failure**

Run:

```powershell
uv run pytest tests/test_delivery_api.py::test_delivery_board_includes_acceptance_runs -q
```

Expected: fail because the board response does not include acceptance data.

- [ ] **Step 3: Add board acceptance payload**

In `list_delivery_board()`, include:

```python
"acceptance_runs": [r.model_dump() for r in service._ws.acceptance_runs.list_all()],
```

Filter by requirement when `requirement_id` is provided:

```python
acceptance_runs = [
    run for run in service._ws.acceptance_runs.list_all()
    if requirement_id is None or run.requirement_id == requirement_id
]
```

- [ ] **Step 4: Add acceptance run endpoint**

Add route:

```python
@router.get("/delivery-plans/{plan_id}/acceptance-runs")
async def list_acceptance_runs(plan_id: str, workspace: str) -> dict:
    service = _get_service(workspace)
    runs = [
        run for run in service._ws.acceptance_runs.list_all()
        if run.plan_id == plan_id
    ]
    runs.sort(key=lambda run: run.created_at)
    return {"runs": [run.model_dump() for run in runs]}
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
uv run pytest tests/test_delivery_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add studio/api/routes/delivery.py tests/test_delivery_api.py
git commit -m "feat: expose delivery acceptance API"
```

## Task 7: Update Delivery Board UI For Acceptance Gate And Bug Loop

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/pages/DeliveryBoard.tsx`
- Modify: `web/src/components/board/DeliveryTaskCard.tsx`

Post-merge MVP adjustment: the merged implementation keeps acceptance UI inline in `DeliveryBoard.tsx` instead of introducing a standalone `AcceptanceGatePanel.tsx`. A standalone panel and artifact drilldown can still be a later UI cleanup.

- [ ] **Step 1: Add frontend types**

Add to `web/src/lib/api.ts`:

```ts
export interface AcceptanceCriterion {
  id: string
  source: string
  text: string
  required_evidence_types: string[]
  severity: 'blocker' | 'major' | 'minor'
  owner_hint: 'dev' | 'art' | 'qa' | 'reviewer' | 'quality'
}

export interface AcceptanceContract {
  id: string
  plan_id: string
  requirement_id: string
  project_id: string
  criteria: AcceptanceCriterion[]
  created_at: string
}

export interface AcceptanceEvidence {
  id: string
  evidence_type: string
  summary: string
  artifact_path?: string | null
  metadata: Record<string, unknown>
}

export interface AcceptanceCriterionResult {
  criterion_id: string
  status: 'passed' | 'failed' | 'inconclusive'
  evidence_ids: string[]
  reason: string
  repair_hint?: string | null
  owner_hint: 'dev' | 'art' | 'qa' | 'reviewer' | 'quality'
  blocking: boolean
}

export interface AcceptanceRun {
  id: string
  contract_id: string
  plan_id: string
  requirement_id: string
  project_id: string
  attempt_number: number
  status: 'running' | 'passed' | 'failed' | 'needs_attention'
  evidence: AcceptanceEvidence[]
  criteria_results: AcceptanceCriterionResult[]
  repair_task_ids: string[]
  created_at: string
  completed_at?: string | null
}
```

Extend board response type with:

```ts
acceptance_runs: AcceptanceRun[]
```

- [ ] **Step 2: Optional follow-up: create standalone AcceptanceGatePanel component**

Create `web/src/components/board/AcceptanceGatePanel.tsx`:

```tsx
import type { AcceptanceContract, AcceptanceRun, DeliveryTask } from '../../lib/types'

interface AcceptanceGatePanelProps {
  contracts: AcceptanceContract[]
  runs: AcceptanceRun[]
  tasks: DeliveryTask[]
}

export function AcceptanceGatePanel({ contracts, runs, tasks }: AcceptanceGatePanelProps) {
  const latestRun = [...runs].sort((a, b) => a.created_at.localeCompare(b.created_at)).at(-1)
  const latestContract = latestRun
    ? contracts.find((contract) => contract.id === latestRun.contract_id)
    : contracts.at(-1)
  const repairTasks = latestRun
    ? tasks.filter((task) => latestRun.repair_task_ids.includes(task.id))
    : []

  if (!latestContract && !latestRun) {
    return (
      <section className="acceptance-gate-panel">
        <h2>Acceptance Gate</h2>
        <p>Waiting for implementation tasks to finish.</p>
      </section>
    )
  }

  return (
    <section className="acceptance-gate-panel">
      <div className="acceptance-gate-header">
        <h2>Acceptance Gate</h2>
        <span>{latestRun ? `${latestRun.status} · attempt ${latestRun.attempt_number}` : 'pending'}</span>
      </div>
      <div className="acceptance-criteria-list">
        {latestContract?.criteria.map((criterion) => {
          const result = latestRun?.criteria_results.find((item) => item.criterion_id === criterion.id)
          return (
            <div className={`acceptance-criterion acceptance-criterion-${result?.status ?? 'pending'}`} key={criterion.id}>
              <div>
                <strong>{criterion.text}</strong>
                <p>{result?.reason ?? 'Not evaluated yet.'}</p>
              </div>
              <span>{result?.status ?? 'pending'}</span>
            </div>
          )
        })}
      </div>
      {latestRun?.evidence.length ? (
        <div className="acceptance-evidence-list">
          <h3>Evidence</h3>
          {latestRun.evidence.map((item) => (
            <div className="acceptance-evidence" key={item.id}>
              <span>{item.evidence_type}</span>
              <p>{item.summary}</p>
            </div>
          ))}
        </div>
      ) : null}
      {repairTasks.length ? (
        <div className="acceptance-repair-list">
          <h3>Bug Loop</h3>
          {repairTasks.map((task) => (
            <div className="acceptance-repair-task" key={task.id}>
              <span>{task.owner_agent}</span>
              <p>{task.title}</p>
              <strong>{task.status}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}
```

- [ ] **Step 3: Optional follow-up: render standalone panel in DeliveryBoard**

In `web/src/pages/DeliveryBoard.tsx`, import and render:

```tsx
import { AcceptanceGatePanel } from '../components/board/AcceptanceGatePanel'
```

Add near the task board:

```tsx
<AcceptanceGatePanel
  contracts={board.acceptance_contracts ?? []}
  runs={board.acceptance_runs ?? []}
  tasks={board.tasks}
/>
```

- [ ] **Step 4: Optional follow-up: add restrained CSS for standalone panel**

Use the existing Delivery board stylesheet. Add classes:

```css
.acceptance-gate-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  background: var(--surface-color);
}

.acceptance-gate-header,
.acceptance-criterion,
.acceptance-evidence,
.acceptance-repair-task {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.acceptance-criteria-list,
.acceptance-evidence-list,
.acceptance-repair-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.acceptance-criterion {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px;
}

.acceptance-criterion-passed {
  border-color: #198754;
}

.acceptance-criterion-failed {
  border-color: #dc3545;
}

.acceptance-criterion-inconclusive {
  border-color: #b58100;
}
```

- [ ] **Step 5: Run frontend checks**

Run:

```powershell
cd web
npm run build
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add web/src/lib/api.ts web/src/pages/DeliveryBoard.tsx web/src/components/board/DeliveryTaskCard.tsx
git commit -m "feat: show delivery acceptance gate"
```

## Task 8: Add Mock Delivery E2E For Acceptance And Repair

**Files:**
- Modify: existing Delivery E2E test file under `web/e2e` or `tests/e2e`
- Modify: Playwright config if screenshot/video retention is not already configured

- [ ] **Step 1: Add E2E fixture project with a startup failure**

Create an E2E helper that seeds a Delivery plan with one done dev task and a project containing:

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "react": "latest",
    "react-dom": "latest"
  },
  "devDependencies": {}
}
```

Create `src/App.tsx` with an intentional runtime error:

```tsx
throw new Error('acceptance smoke failure')
```

- [ ] **Step 2: Assert gate fails and creates bug task**

The E2E test should:

```ts
await page.goto('/delivery')
await expect(page.getByText('Acceptance Gate')).toBeVisible()
await expect(page.getByText(/failed|repairing/i)).toBeVisible()
await expect(page.getByText(/Fix acceptance failure/i)).toBeVisible()
```

- [ ] **Step 3: Add a success fixture**

Use a minimal app:

```tsx
export default function App() {
  return <main data-game-root>Snake MVP Ready</main>
}
```

Assert:

```ts
await expect(page.getByText(/passed|accepted/i)).toBeVisible()
await expect(page.getByText('The browser page opens without fatal page errors.')).toBeVisible()
```

- [ ] **Step 4: Ensure screenshots and videos are retained**

In Playwright config, keep:

```ts
use: {
  screenshot: 'on',
  video: 'on',
  trace: 'on-first-retry',
}
```

- [ ] **Step 5: Run E2E**

Run the existing E2E command used by the repo. If the repo uses the web package:

```powershell
cd web
npm run test:e2e
```

Expected: the acceptance failure test captures screenshots and video; the success test reaches accepted.

- [ ] **Step 6: Commit**

```powershell
git add web tests
git commit -m "test: cover delivery acceptance gate e2e"
```

## Task 9: Final Verification

**Files:**
- All files touched in previous tasks

- [ ] **Step 1: Run backend test slice**

```powershell
uv run pytest tests/test_acceptance_schemas.py tests/test_acceptance_contract.py tests/test_acceptance_verifier.py tests/test_acceptance_evaluator.py tests/test_delivery_acceptance_graph.py tests/test_delivery_graph.py tests/test_delivery_api.py -q
```

Expected: pass.

- [ ] **Step 2: Run full backend suite**

```powershell
uv run pytest -q
```

Expected: pass.

- [ ] **Step 3: Run frontend build**

```powershell
cd web
npm run build
```

Expected: pass.

- [ ] **Step 4: Run E2E**

```powershell
cd web
npm run test:e2e
```

Expected: pass with screenshots and videos retained.

- [ ] **Step 5: Inspect git status**

```powershell
git status --short
```

Expected: only intended implementation files are changed before final commit.

## Self-Review

- Spec coverage: schemas, contract builder, verifier, evaluator, graph integration, API, board UI, and E2E are covered.
- Placeholder scan: this plan contains concrete files, commands, status names, schema fields, and code snippets.
- Type consistency: `AcceptanceContract`, `AcceptanceRun`, `AcceptanceCriterionResult`, `AcceptanceEvidence`, `task_kind`, and plan statuses are named consistently across backend, API, and frontend tasks.
- Completion invariant: no task in this plan allows a requirement to reach `done` before acceptance passes.
