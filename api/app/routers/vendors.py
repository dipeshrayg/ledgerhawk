from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.negotiation_agent import negotiate
from app.agents.report_agent import dispute_letter
from app.config import settings
from app.db import get_db
from app.db_adapter import invoice_rows_to_pydantic, usage_rows_to_pydantic, vendor_ast_dsl
from app.models_db import Vendor
from app.pipeline import precedence, reconciliation
from app.pipeline.contract_tests_runner import run_contract_tests
from app.pipeline.forecast import add_month
from app.pipeline.loader import load_benchmarks

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def _get_vendor(db: Session, vendor_id: str) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
    if vendor is None:
        raise HTTPException(404, f"Vendor '{vendor_id}' not found")
    return vendor


@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).all()
    out = []
    for v in vendors:
        ast, dsl = vendor_ast_dsl(v)
        usage = usage_rows_to_pydantic(v.usage_periods)
        invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
        results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
        failing = [r for r in results if r.findings]
        out.append({
            "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "category": v.category,
            "invoice_count": len(invoices), "finding_count": len(failing),
            "total_recovered": str(sum((r.findings[0].delta for r in failing), __import__("decimal").Decimal("0.00"))),
            "build_status": "FAIL" if failing else "PASS",
        })
    return {"vendors": out, "demo_mode": settings.is_demo_mode, "llm_mode": settings.llm_mode}


@router.get("/{vendor_id}")
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    return {"vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "category": v.category,
            "ast": ast.model_dump(mode="json"), "dsl": dsl.model_dump(mode="json")}


@router.get("/{vendor_id}/rule-inspector")
def rule_inspector(vendor_id: str, as_of: str | None = None, db: Session = Depends(get_db)):
    """F12 -- the compiled effective terms, with provenance (which document
    each rule came from), as of a given date (defaults to today)."""
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    as_of_date = date.fromisoformat(as_of) if as_of else settings.demo_today
    resolved = precedence.resolve_effective_terms(dsl, as_of_date, ast.documents)
    return {
        "vendor_id": vendor_id, "as_of": str(as_of_date),
        "effective_terms": [
            {
                "rule_key": key, "rule_type": er.rule.rule_type.value, "params": er.rule.params,
                "source_name": er.rule.source_name, "doc_id": er.rule.doc_id,
                "effective_from": str(er.rule.effective_from), "effective_to": str(er.rule.effective_to) if er.rule.effective_to else None,
                "provenance_quote": er.rule.provenance.quote, "provenance_section": er.rule.provenance.section,
                "superseded_rule_ids": er.superseded,
            }
            for key, er in resolved.items()
        ],
        "documents": [d.model_dump(mode="json") for d in ast.documents],
    }


@router.get("/{vendor_id}/reconcile")
def reconcile_vendor(vendor_id: str, db: Session = Depends(get_db)):
    """F1 core loop -- PASS/FAIL per invoice with full evidence."""
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
    results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
    return {"vendor_id": vendor_id, "results": [r.model_dump(mode="json") for r in results]}


@router.get("/{vendor_id}/findings")
def vendor_findings(vendor_id: str, db: Session = Depends(get_db)):
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
    results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
    findings = [r.findings[0].model_dump(mode="json") for r in results if r.findings]
    return {"vendor_id": vendor_id, "findings": findings}


@router.get("/{vendor_id}/contract-tests")
def vendor_contract_tests(vendor_id: str, db: Session = Depends(get_db)):
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    report = run_contract_tests(v.contract_tests_yaml, dsl, ast.documents)
    return report.model_dump(mode="json") | {"all_passed": report.all_passed, "pass_count": report.pass_count, "fail_count": report.fail_count}


@router.get("/{vendor_id}/invoices/{invoice_id}/dispute-letter")
def get_dispute_letter(vendor_id: str, invoice_id: str, db: Session = Depends(get_db)):
    """F1 -- generates a dispute letter for a specific failing invoice.
    Every fact in the letter (clause quote, rule, math trace, dollar delta)
    is copied verbatim from the computed Finding; the LLM (if available)
    only polishes prose around them."""
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
    invoice = next((i for i in invoices if i.invoice_id == invoice_id), None)
    if invoice is None:
        raise HTTPException(404, f"Invoice '{invoice_id}' not found")
    results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
    result = next(r for r in results if r.invoice_id == invoice_id)
    if not result.findings:
        raise HTTPException(400, "This invoice has no findings -- nothing to dispute")
    letter = dispute_letter(result.findings[0], v.vendor_name, invoice)
    return {"vendor_id": vendor_id, "invoice_id": invoice_id, "letter": letter, "finding": result.findings[0].model_dump(mode="json")}


@router.post("/{vendor_id}/negotiate")
def vendor_negotiate(vendor_id: str, db: Session = Depends(get_db)):
    """F5 -- Negotiation AI for an existing signed vendor: alternative
    terms, negotiation email, risk score, expected savings vs. benchmark."""
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    if not usage:
        raise HTTPException(400, "No usage history for this vendor")
    benchmarks = load_benchmarks()
    baseline = usage[-1]
    start = add_month(baseline.period_start)
    result = negotiate(ast, dsl, v.category, benchmarks, baseline, start, months=36)
    return {"vendor_id": vendor_id, **result}


@router.get("/{vendor_id}/ci-history")
def vendor_ci_history(vendor_id: str, db: Session = Depends(get_db)):
    """F9 -- CI-style history log per vendor + an overall build-status badge."""
    v = _get_vendor(db, vendor_id)
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
    results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
    test_report = run_contract_tests(v.contract_tests_yaml, dsl, ast.documents)

    history = [
        {
            "invoice_id": r.invoice_id, "status": r.status, "expected_total": str(r.expected_total),
            "actual_total": str(r.actual_total),
            "delta": str(r.findings[0].delta) if r.findings else "0.00",
        }
        for r in sorted(results, key=lambda r: r.invoice_id)
    ]
    overall_status = "FAIL" if (any(h["status"] == "FAIL" for h in history) or not test_report.all_passed) else "PASS"
    return {
        "vendor_id": vendor_id, "build_status": overall_status, "history": history,
        "contract_tests": {"pass_count": test_report.pass_count, "fail_count": test_report.fail_count, "all_passed": test_report.all_passed},
    }
