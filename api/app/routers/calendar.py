from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.db_adapter import vendor_ast_dsl
from app.models_db import Vendor
from app.pipeline.renewal import next_anniversary as _next_anniversary
from app.pipeline.renewal import next_renewal_date as _next_renewal_date

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("")
def renewal_risk_calendar(db: Session = Depends(get_db)):
    """F7 -- timeline of every vendor's renewals, discount/credit expiries,
    escalation effective dates, and auto-renewal notice deadlines, each
    with a days-remaining badge."""
    today = settings.demo_today
    events = []

    for v in db.query(Vendor).all():
        ast, dsl = vendor_ast_dsl(v)
        term = ast.term
        renewal_date = _next_renewal_date(term.end_date, term.renewal_type, today)

        events.append({
            "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "type": "renewal",
            "date": str(renewal_date), "days_remaining": (renewal_date - today).days,
            "description": f"Contract renews ({term.renewal_type.value}){' with a ' + str(term.auto_renewal_uplift_pct) + '% uplift' if term.auto_renewal_uplift_pct else ''}.",
            "projected_cost_impact_pct": term.auto_renewal_uplift_pct,
        })
        if term.renewal_notice_days:
            deadline = date.fromordinal(renewal_date.toordinal() - term.renewal_notice_days)
            events.append({
                "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "type": "renewal_notice_deadline",
                "date": str(deadline), "days_remaining": (deadline - today).days,
                "description": f"Last day to send non-renewal notice ({term.renewal_notice_days}-day window).",
                "projected_cost_impact_pct": None,
            })

        for rule in dsl.rules:
            if rule.rule_type.value == "discount" and rule.effective_to and rule.effective_to >= today:
                events.append({
                    "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "type": "discount_expiry",
                    "date": str(rule.effective_to), "days_remaining": (rule.effective_to - today).days,
                    "description": f"Discount ({rule.source_name}) expires.",
                    "projected_cost_impact_pct": float(rule.params.get("pct", 0)) if "pct" in rule.params else None,
                })
            if rule.rule_type.value == "credit" and rule.effective_to and rule.effective_to >= today:
                events.append({
                    "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "type": "credit_expiry",
                    "date": str(rule.effective_to), "days_remaining": (rule.effective_to - today).days,
                    "description": f"Service credit ({rule.source_name}) expires.",
                    "projected_cost_impact_pct": None,
                })
            if rule.rule_type.value == "escalation":
                next_date = _next_anniversary(rule.effective_from, today)
                events.append({
                    "vendor_id": v.vendor_id, "vendor_name": v.vendor_name, "type": "escalation_effective",
                    "date": str(next_date), "days_remaining": (next_date - today).days,
                    "description": f"Next scheduled escalation ({rule.source_name}, +{rule.params.get('pct')}%).",
                    "projected_cost_impact_pct": float(rule.params.get("pct", 0)),
                })

    events.sort(key=lambda e: e["days_remaining"])
    return {"today": str(today), "events": events}
