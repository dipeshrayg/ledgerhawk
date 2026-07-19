from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.csv_watcher import CSVDropFolderConnector
from app.connectors.mock_erp import MockERPConnector
from app.connectors.stripe_sandbox import StripeSandboxConnector
from app.db import get_db
from app.db_adapter import usage_rows_to_pydantic, vendor_ast_dsl
from app.models_db import CIRun, InvoiceRow, Vendor
from app.pipeline import reconciliation
from app.pipeline.contract_tests_runner import run_contract_tests
from app.pipeline.loader import DATA_DIR

router = APIRouter(prefix="/api/connectors", tags=["connectors"])

_mock_erp = MockERPConnector()
_csv_watcher = CSVDropFolderConnector(DATA_DIR / "dropfolder")


def _log_ci_run(db: Session, vendor: Vendor, ast, dsl, invoice) -> dict:
    usage = usage_rows_to_pydantic(vendor.usage_periods)
    expected_series = reconciliation.compute_expected_series(dsl, ast.documents, usage)
    match = next((e for e in expected_series if e.period_start == invoice.period_start), None)
    if match is None:
        return {"invoice_id": invoice.invoice_id, "status": "SKIPPED", "reason": "no matching usage period"}
    result = reconciliation.reconcile_invoice(vendor.vendor_id, invoice, match)
    test_report = run_contract_tests(vendor.contract_tests_yaml, dsl, ast.documents)
    ci_run = CIRun(
        vendor_id=vendor.vendor_id, invoice_id=invoice.invoice_id, status=result.status,
        expected_total=result.expected_total, actual_total=result.actual_total,
        delta=result.findings[0].delta if result.findings else 0, contract_tests_passed=test_report.all_passed,
        ran_at=datetime.now(timezone.utc),
    )
    db.add(ci_run)
    db.commit()
    return {"invoice_id": invoice.invoice_id, "status": result.status,
            "delta": str(result.findings[0].delta) if result.findings else "0.00"}


@router.get("")
def list_connectors():
    return {"connectors": [
        {"name": "mock_erp", "type": "streaming", "enabled": True, "description": "Simulates a live ERP feed by replaying seeded invoice history."},
        {"name": "csv_drop_folder", "type": "file_watch", "enabled": True, "description": f"Watches {DATA_DIR / 'dropfolder'} for new invoice CSVs.", "folder": str(DATA_DIR / "dropfolder")},
        {"name": "stripe_sandbox", "type": "api", "enabled": settings.stripe_api_key is not None, "description": "Pulls invoices from a Stripe sandbox account (requires STRIPE_API_KEY)."},
    ]}


@router.post("/mock-erp/poll")
def poll_mock_erp(db: Session = Depends(get_db)):
    """F3 -- simulates one tick of a live ERP feed. Each new invoice is
    immediately run through Contract CI (F9)."""
    invoices = _mock_erp.poll()
    results = []
    for inv in invoices:
        vendor = db.query(Vendor).filter(Vendor.vendor_id == inv.vendor_id).first()
        if vendor is None:
            continue
        ast, dsl = vendor_ast_dsl(vendor)
        results.append(_log_ci_run(db, vendor, ast, dsl, inv))
    return {"polled": len(invoices), "remaining": _mock_erp.remaining(), "results": results}


@router.post("/mock-erp/reset")
def reset_mock_erp():
    _mock_erp.reset()
    return {"remaining": _mock_erp.remaining()}


@router.post("/csv-watch/poll")
def poll_csv_watcher(db: Session = Depends(get_db)):
    """F3 -- checks the drop folder for new invoice CSVs and ingests any
    found, running Contract CI on each."""
    invoices = _csv_watcher.poll()
    results = []
    for inv in invoices:
        vendor = db.query(Vendor).filter(Vendor.vendor_id == inv.vendor_id).first()
        if vendor is None:
            results.append({"invoice_id": inv.invoice_id, "status": "ERROR", "reason": f"unknown vendor_id '{inv.vendor_id}'"})
            continue
        db.add(InvoiceRow(
            vendor_pk=vendor.id, invoice_id=inv.invoice_id, period_start=inv.period_start, period_end=inv.period_end,
            invoice_date=inv.invoice_date, line_items_json=[li.model_dump(mode="json") for li in inv.line_items],
            total_amount=inv.total_amount, source="csv",
        ))
        db.commit()
        ast, dsl = vendor_ast_dsl(vendor)
        results.append(_log_ci_run(db, vendor, ast, dsl, inv))
    return {"polled": len(invoices), "results": results}


@router.get("/stripe/status")
def stripe_status():
    connector = StripeSandboxConnector()
    return {"enabled": connector.enabled}
