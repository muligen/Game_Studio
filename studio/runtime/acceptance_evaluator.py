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
    if criterion.source == "system":
        return _evaluate_system_criterion(criterion, verification, matching_evidence, blocking)
    if _is_launch_target_failure(verification):
        return _deferred_until_startup_fixed(criterion)
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


def _evaluate_system_criterion(
    criterion: AcceptanceCriterion,
    verification: VerificationResult,
    matching_evidence: list,
    blocking: bool,
) -> AcceptanceCriterionResult:
    text = criterion.text.lower()
    if _is_launch_target_failure(verification) and "detectable command" not in text:
        return _deferred_until_startup_fixed(criterion)
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


def _deferred_until_startup_fixed(criterion: AcceptanceCriterion) -> AcceptanceCriterionResult:
    return AcceptanceCriterionResult(
        criterion_id=criterion.id,
        status="inconclusive",
        evidence_ids=[],
        reason="Startup entry point validation must pass before this criterion can be evaluated.",
        repair_hint=f"Evaluate after startup is fixed: {criterion.text}",
        owner_hint=criterion.owner_hint,
        blocking=False,
    )


def _is_launch_target_failure(verification: VerificationResult) -> bool:
    if verification.startup_ok:
        return False
    error_text = "\n".join(verification.errors).lower()
    if any(marker in error_text for marker in ("pageerror:", "console:")):
        return False
    return any(
        marker in error_text
        for marker in (
            "package.json",
            "index.html",
            "preview command missing",
            "no working start or preview",
        )
    )


def _has_fallback_warning(task_results: list[dict[str, object]]) -> bool:
    for result in task_results:
        warnings = result.get("context_warnings", [])
        if isinstance(warnings, list) and any("fallback" in str(item).lower() for item in warnings):
            return True
    return False
