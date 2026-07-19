
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.negotiation_agent import negotiate
from app.agents.risk_agent import assess
from app.db import get_db
from app.models_db import ProposalRow
from app.pipeline.contract_tests_runner import run_contract_tests
from app.pipeline.loader import load_benchmarks
from app.schemas.ast import ContractAST
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import PricingDSL

router = APIRouter(prefix="/api/presign", tags=["presign"])

DEFAULT_BASELINE_EMPLOYEES = 600


def _get_proposal(db: Session, proposal_id: str) -> ProposalRow:
    row = db.query(ProposalRow).filter(ProposalRow.proposal_id == proposal_id).first()
    if row is None:
        raise HTTPException(404, f"Proposal '{proposal_id}' not found")
    return row


@router.get("/{proposal_id}")
def presign_review(proposal_id: str, seats: int | None = None, db: Session = Depends(get_db)):
    """F4 -- Pre-Sign Review: Static Validator lints + benchmark comparison
    + 3-year cost projection vs market-standard terms, plus a real,
    computed contract-test run (the proposal has a deliberately failing
    test)."""
    row = _get_proposal(db, proposal_id)
    ast = ContractAST.model_validate(row.ast_json)
    dsl = PricingDSL.model_validate(row.dsl_json)
    benchmarks = load_benchmarks()
    bench = benchmarks.get("categories", {}).get(row.category, {})

    risk = assess(ast, dsl)
    baseline = UsagePeriod(period_start=ast.term.start_date, period_end=ast.term.start_date,
                            units={"employee": seats or DEFAULT_BASELINE_EMPLOYEES})
    neg = negotiate(ast, dsl, row.category, benchmarks, baseline, ast.term.start_date, months=36)
    test_report = run_contract_tests(row.contract_tests_yaml, dsl, ast.documents)

    return {
        "proposal_id": proposal_id, "vendor_name": row.vendor_name, "category": row.category,
        "risk_score": risk["risk_score"], "lints": risk["lints"], "summary": risk["summary"],
        "benchmark": bench,
        "projected_cost_36mo": neg["current_projected_total_36mo"],
        "benchmark_compliant_cost_36mo": neg["benchmark_projected_total_36mo"],
        "estimated_3yr_impact": neg["expected_savings_36mo"],
        "contract_tests": {
            "results": [r.model_dump(mode="json") for r in test_report.results],
            "pass_count": test_report.pass_count, "fail_count": test_report.fail_count, "all_passed": test_report.all_passed,
        },
    }


@router.post("/{proposal_id}/negotiate")
def presign_negotiate(proposal_id: str, seats: int | None = None, db: Session = Depends(get_db)):
    """F5 -- Negotiation AI: alternative terms, negotiation email, risk
    score, and expected savings."""
    row = _get_proposal(db, proposal_id)
    ast = ContractAST.model_validate(row.ast_json)
    dsl = PricingDSL.model_validate(row.dsl_json)
    benchmarks = load_benchmarks()
    baseline = UsagePeriod(period_start=ast.term.start_date, period_end=ast.term.start_date,
                            units={"employee": seats or DEFAULT_BASELINE_EMPLOYEES})
    result = negotiate(ast, dsl, row.category, benchmarks, baseline, ast.term.start_date, months=36)
    return {"proposal_id": proposal_id, **result}
