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
