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
