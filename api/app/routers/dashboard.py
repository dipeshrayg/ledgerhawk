from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.db_adapter import invoice_rows_to_pydantic, usage_rows_to_pydantic, vendor_ast_dsl
from app.models_db import Vendor
from app.pipeline import reconciliation
from app.pipeline.forecast import add_month, forecast_series
from app.pipeline.renewal import next_renewal_date
from app.pipeline.violation_graph import ViolationGraph

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def cfo_dashboard(db: Session = Depends(get_db)):
    """F11 -- the executive landing view: recovered money, forecasted
    leakage, upcoming renewals, compliance %, vendor risk ranking, top
    violating clauses, and a monthly trend series."""
    vendors = db.query(Vendor).all()
    all_findings = []
    vendor_names = {}
    invoice_counts = {}
    monthly_recovered: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    upcoming_renewals = []
    forecasted_annual_leakage = Decimal("0.00")

    for v in vendors:
        vendor_names[v.vendor_id] = v.vendor_name
        ast, dsl = vendor_ast_dsl(v)
        usage = usage_rows_to_pydantic(v.usage_periods)
        invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
        invoice_counts[v.vendor_id] = len(invoices)
        results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
        for r in results:
            if r.findings:
                f = r.findings[0]
                all_findings.append(f)
                monthly_recovered[str(r.findings[0].invoice_id)[-6:]] += f.delta

        renewal_date = next_renewal_date(ast.term.end_date, ast.term.renewal_type, settings.demo_today)
        days_to_renewal = (renewal_date - settings.demo_today).days
        if 0 <= days_to_renewal <= 90:
            upcoming_renewals.append({
                "vendor_id": v.vendor_id, "vendor_name": v.vendor_name,
                "renewal_date": str(renewal_date), "days_remaining": days_to_renewal,
                "auto_renewal_uplift_pct": ast.term.auto_renewal_uplift_pct,
            })

        if usage:
            last_usage = usage[-1]
            forecast_start = add_month(last_usage.period_start)
            series = forecast_series(ast, dsl, last_usage, forecast_start, months=12)
            forecasted_annual_leakage += sum((inv.total for inv in series), Decimal("0.00")) - series[0].total * 12

    graph = ViolationGraph(all_findings, vendor_names)
    total_invoices = sum(invoice_counts.values())
    failing_invoices = len({(f.vendor_id, f.invoice_id) for f in all_findings})
    compliance_pct = round((total_invoices - failing_invoices) / total_invoices * 100, 1) if total_invoices else 100.0

    monthly_trend = [{"month": k, "recovered": str(v)} for k, v in sorted(monthly_recovered.items())]

    return {
        "demo_mode": settings.is_demo_mode,
        "llm_mode": settings.llm_mode,
        "total_recovered": str(graph.total_recovered()),
        "forecasted_12mo_leakage_delta": str(forecasted_annual_leakage),
        "compliance_pct": compliance_pct,
        "total_invoices": total_invoices,
        "failing_invoices": failing_invoices,
        "vendor_risk_ranking": graph.vendor_risk_ranking(),
        "top_violating_clauses": graph.top_clauses_by_loss(5),
        "upcoming_renewals_90d": sorted(upcoming_renewals, key=lambda r: r["days_remaining"]),
        "monthly_trend": monthly_trend,
        "vendor_count": len(vendors),
    }
