"""Leakage Forecast (F2) -- deterministic 36-month replay forward.

No ML, no prediction: this replays the *same* compiled DSL the Billing
Engine already uses, holding usage constant at the last known baseline, and
mechanically applies whatever is already scheduled to happen -- escalations
crossing anniversaries, discounts expiring, and (if the contract term
carries one) an auto-renewal uplift. Every number is exactly as provable as
a reconciliation finding; it's just dated in the future.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from app.pipeline import billing_engine, precedence
from app.schemas.ast import ContractAST, ContractTerm, RenewalType
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import PricingDSL, Rule


def add_month(d: date) -> date:
    y, m = d.year, d.month
    m += 1
    if m > 12:
        m = 1
        y += 1
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last_day))


def renewal_uplift_multiplier(term: ContractTerm, as_of: date) -> Decimal:
    """Auto-renewal uplifts compound each time the term's anniversary is
    crossed, for as long as the contract keeps auto-renewing."""
    if term.renewal_type != RenewalType.AUTO or not term.auto_renewal_uplift_pct:
        return Decimal("1")
    if as_of < term.end_date:
        return Decimal("1")
    years_since = as_of.year - term.end_date.year - (
        1 if (as_of.month, as_of.day) < (term.end_date.month, term.end_date.day) else 0
    )
    renewals_passed = max(0, years_since) + 1
    pct = Decimal(str(term.auto_renewal_uplift_pct))
    return (Decimal("1") + pct / Decimal("100")) ** renewals_passed


def _scale_rule(rule: Rule, multiplier: Decimal) -> Rule:
    if multiplier == 1:
        return rule
    params = dict(rule.params)
    if rule.rule_type.value == "per_unit":
        params["rate"] = str((Decimal(params["rate"]) * multiplier).quantize(Decimal("0.0001")))
    elif rule.rule_type.value == "flat_fee":
        params["amount"] = str((Decimal(params["amount"]) * multiplier).quantize(Decimal("0.0001")))
    elif rule.rule_type.value == "volume_tier":
        params = {**params, "tiers": [
            {**t, "rate": str((Decimal(t["rate"]) * multiplier).quantize(Decimal("0.0001")))} for t in params["tiers"]
        ]}
    else:
        return rule
    return rule.model_copy(update={"params": params})


def forecast_series(ast: ContractAST, dsl: PricingDSL, baseline_usage: UsagePeriod, start: date, months: int = 36):
    """Replays `months` periods forward from `start`, holding usage at
    `baseline_usage`'s seats/units constant. Returns a list of ExpectedInvoice.

    Deliberately ignores each document's `executed` flag: forecasting (and
    Pre-Sign Review's "what would this cost if signed" projection) is
    inherently hypothetical, unlike reconciliation, which must never let an
    unsigned draft govern a real invoice.
    """
    results = []
    balance = Decimal("0.00")
    period_start = start
    for _ in range(months):
        last_day = calendar.monthrange(period_start.year, period_start.month)[1]
        period_end = date(period_start.year, period_start.month, last_day)
        effective = precedence.effective_rules_dict(dsl, period_start, documents=None)
        multiplier = renewal_uplift_multiplier(ast.term, period_start)
        effective = {k: _scale_rule(r, multiplier) for k, r in effective.items()}
        usage = UsagePeriod(period_start=period_start, period_end=period_end,
                            seats=baseline_usage.seats, units=dict(baseline_usage.units))
        invoice, balance = billing_engine.compute_expected_invoice(effective, usage, period_start, period_end, balance)
        invoice.vendor_id = dsl.vendor_id
        results.append(invoice)
        period_start = add_month(period_start)
    return results


def leakage_headline(ast: ContractAST, dsl: PricingDSL, baseline_usage: UsagePeriod, start: date, months: int = 36) -> dict:
    """Finds the single largest month-over-month cost jump in the forecast
    window and annualizes it -- the number the CFO Dashboard headline and
    per-vendor forecast chart both key off of."""
    series = forecast_series(ast, dsl, baseline_usage, start, months)
    best = None
    for i in range(1, len(series)):
        prev, curr = series[i - 1], series[i]
        jump = curr.total - prev.total
        if jump > 0 and (best is None or jump > best["jump"]):
            best = {"month_index": i, "period_start": curr.period_start, "jump": jump}

    result = {
        "series": [{"period_start": str(inv.period_start), "total": str(inv.total)} for inv in series],
        "start_total": str(series[0].total) if series else None,
        "end_total": str(series[-1].total) if series else None,
    }
    if best is None:
        result["headline"] = None
        return result

    annualized_delta = best["jump"] * 12
    result.update({
        "month_index": best["month_index"],
        "jump_period_start": str(best["period_start"]),
        "monthly_jump": str(best["jump"]),
        "annualized_impact": str(annualized_delta),
        "headline": (
            f"In {best['month_index']} months ({best['period_start']:%B %Y}), {dsl.vendor_id}'s cost jumps by "
            f"${best['jump']:,.2f}/mo -- an estimated ${annualized_delta:,.2f}/yr impact."
        ),
    })
    return result
