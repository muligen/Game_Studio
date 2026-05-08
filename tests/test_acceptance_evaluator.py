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


def test_startup_failure_defers_requirement_criteria_until_startup_is_fixed():
    contract = AcceptanceContract(
        id="contract_plan_001",
        plan_id="plan_001",
        requirement_id="req_001",
        project_id="proj_001",
        criteria=[
            AcceptanceCriterion(
                id="crit_detectable_start",
                source="system",
                text="The project exposes a detectable command to start or preview the game.",
                required_evidence_types=["command"],
                severity="blocker",
                owner_hint="dev",
            ),
            AcceptanceCriterion(
                id="crit_browser",
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

    run = evaluate_acceptance(
        contract=contract,
        verification=VerificationResult(startup_ok=False, browser_ok=False, errors=["package.json missing"]),
        task_results=[],
        run_id="acc_run_001",
        attempt_number=1,
    )

    blocking_failures = [result for result in run.criteria_results if result.blocking and result.status != "passed"]
    assert [result.criterion_id for result in blocking_failures] == ["crit_detectable_start"]

    deferred = {result.criterion_id: result for result in run.criteria_results}
    assert deferred["crit_browser"].status == "inconclusive"
    assert deferred["crit_browser"].blocking is False
    assert deferred["crit_controls"].status == "inconclusive"
    assert deferred["crit_controls"].blocking is False


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
