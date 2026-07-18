"""The Virtual Billing Engine - the only code in LedgerHawk allowed to
multiply a rate by a quantity. Deterministic, Decimal-only, no LLM calls,
no network, no randomness. Given a set of *already precedence-resolved*
effective rules (one winning Rule per rule_key - see
app/pipeline/precedence.py) and a period's usage, it computes exactly what
should have been billed, to the cent, with a full arithmetic trace.

Kept decoupled from precedence resolution on purpose: this module is
unit-tested against hand-built rule dicts with no document/precedence
machinery involved.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.schemas.billing import ExpectedCharge, ExpectedInvoice, UsagePeriod
from app.schemas.dsl import ProrationMethod, Rule

CENTS = Decimal("0.01")


def q(x: Decimal) -> Decimal:
    """Round to cents, half-up - the only rounding rule in the codebase."""
    return x.quantize(CENTS, rounding=ROUND_HALF_UP)


def _dec(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def days_in_period(period_start: date, period_end: date) -> int:
    return (period_end - period_start).days + 1


def escalated_rate(base_rate: Decimal, escalation: Optional[Rule], as_of: date) -> tuple[Decimal, list[str]]:
    """Applies a scheduled, capped escalation to a base rate.

    Escalation is additive-percentage-of-base per elapsed anniversary,
    capped cumulatively (uncapped if `cap_pct` is absent from params -
    the Static Validator is what flags that as a risk, not this engine).
    """
    if escalation is None:
        return base_rate, []
    pct = _dec(escalation.params["pct"])
    cap_pct = escalation.params.get("cap_pct")
    cap = _dec(cap_pct) if cap_pct is not None else None
    start = escalation.effective_from
    years = as_of.year - start.year - (1 if (as_of.month, as_of.day) < (start.month, start.day) else 0)
    years = max(0, years)
    cumulative = pct * years
    capped_note = ""
    if cap is not None and cumulative > cap:
        cumulative = cap
        capped_note = f" (capped at {cap}%)"
    rate = base_rate * (Decimal("1") + cumulative / Decimal("100"))
    trace = [
        f"Escalation from {start.isoformat()}: {years} anniversary(ies) x {pct}%"
        f" = {pct * years}% cumulative{capped_note} -> rate {base_rate} x "
        f"(1 + {cumulative}/100) = {q(rate)}"
    ]
    return q(rate), trace


def _prorated_fraction(period_start: date, period_end: date, active_start: date, active_end: date) -> Decimal:
    total_days = days_in_period(period_start, period_end)
    overlap_start = max(period_start, active_start)
    overlap_end = min(period_end, active_end)
    active_days = max(0, (overlap_end - overlap_start).days + 1)
    return Decimal(active_days) / Decimal(total_days)


def per_unit_charge(
    rule: Rule,
    escalation: Optional[Rule],
    proration: ProrationMethod,
    usage: UsagePeriod,
    period_start: date,
    period_end: date,
) -> tuple[Decimal, list[str]]:
    unit_name = rule.params["unit_name"]
    base_rate = _dec(rule.params["rate"])
    quantity = usage.seats if unit_name == "seat" else usage.units.get(unit_name, 0)
    quantity = quantity or 0

    change = usage.seat_change if unit_name == "seat" else None
    if change and proration == ProrationMethod.DAILY:
        change_date = change["date"] if isinstance(change["date"], date) else date.fromisoformat(change["date"])
        rate, esc_trace = escalated_rate(base_rate, escalation, period_start)
        frac_before = _prorated_fraction(period_start, period_end, period_start, change_date - timedelta(days=1))
        frac_after = _prorated_fraction(period_start, period_end, change_date, period_end)
        amount = q(rate * quantity * frac_before) + q(rate * change["new_seats"] * frac_after)
        trace = esc_trace + [
            f"Mid-period change on {change_date.isoformat()}: {quantity} {unit_name}(s) x {rate} x "
            f"{frac_before:.4f} of period + {change['new_seats']} {unit_name}(s) x {rate} x {frac_after:.4f} "
            f"of period = {amount}"
        ]
        return amount, trace

    if change and proration != ProrationMethod.DAILY:
        # Contract doesn't require daily proration -> bill the post-change
        # quantity for the whole period (full_month / none semantics).
        quantity = change["new_seats"]

    rate, esc_trace = escalated_rate(base_rate, escalation, period_start)
    amount = q(rate * quantity)
    trace = esc_trace + [f"{quantity} {unit_name}(s) x {rate} = {amount}"]
    return amount, trace


def volume_tier_charge(rule: Rule, usage: UsagePeriod, period_start: date) -> tuple[Decimal, list[str]]:
    unit_name = rule.params["unit_name"]
    quantity = usage.units.get(unit_name, 0) or 0
    tiers = rule.params["tiers"]
    remaining = quantity
    total = Decimal("0")
    trace = []
    for tier in sorted(tiers, key=lambda t: t["min_units"]):
        min_u, max_u, rate = tier["min_units"], tier.get("max_units"), _dec(tier["rate"])
        tier_capacity = (max_u - min_u + 1) if max_u is not None else None
        units_in_tier = min(remaining, tier_capacity) if tier_capacity is not None else remaining
        if units_in_tier <= 0:
            continue
        tier_amount = q(rate * units_in_tier)
        total += tier_amount
        trace.append(f"Tier [{min_u}-{max_u or '∞'}]: {units_in_tier} x {rate} = {tier_amount}")
        remaining -= units_in_tier
        if remaining <= 0:
            break
    return q(total), trace


def flat_fee_charge(rule: Rule, period_start: date, period_end: date) -> tuple[Decimal, list[str]]:
    amount = _dec(rule.params["amount"])
    cadence = rule.params.get("cadence", "monthly")
    if cadence == "annual":
        anniv_month, anniv_day = rule.effective_from.month, rule.effective_from.day
        in_period = any(
            d.month == anniv_month and d.day == anniv_day
            for d in _iter_days(period_start, period_end)
        )
        if not in_period:
            return Decimal("0.00"), [f"Annual flat fee not due in {period_start:%b %Y}"]
    return q(amount), [f"Flat fee ({cadence}) = {q(amount)}"]


def _iter_days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def one_time_charges(rules: dict[str, Rule], period_start: date, period_end: date) -> list[tuple[str, Decimal, list[str], Rule]]:
    out = []
    for key, rule in rules.items():
        if rule.rule_type.value != "one_time":
            continue
        charge_date = rule.params.get("date")
        d = date.fromisoformat(charge_date) if isinstance(charge_date, str) else charge_date
        if period_start <= d <= period_end:
            amt = q(_dec(rule.params["amount"]))
            out.append((key, amt, [f"One-time charge '{rule.params.get('description', key)}' on {d.isoformat()} = {amt}"], rule))
    return out


def compute_expected_invoice(
    effective_rules: dict[str, Rule],
    usage: UsagePeriod,
    period_start: date,
    period_end: date,
    credit_balance_in: Decimal = Decimal("0.00"),
) -> tuple[ExpectedInvoice, Decimal]:
    """Computes the expected invoice for one billing period.

    Returns (ExpectedInvoice, credit_balance_out) - the latter threads
    rollover credit forward when the caller replays multiple periods in
    sequence (reconciliation and forecasting both do this).
    """
    proration = ProrationMethod(
        effective_rules.get("pricing.proration_policy", None).params["method"]
        if "pricing.proration_policy" in effective_rules
        else "none"
    )
    escalation = effective_rules.get("pricing.escalation.default")

    charges: list[ExpectedCharge] = []
    recurring_subtotal = Decimal("0.00")

    for key, rule in effective_rules.items():
        rt = rule.rule_type.value
        if rt == "per_unit":
            amount, trace = per_unit_charge(rule, escalation, proration, usage, period_start, period_end)
            charges.append(ExpectedCharge(
                rule_id=rule.rule_id, rule_key=key, description=f"{rule.params['unit_name']} usage",
                amount=amount, math_trace=trace,
                provenance_quote=rule.provenance.quote, provenance_source=rule.source_name,
            ))
            recurring_subtotal += amount
        elif rt == "volume_tier":
            amount, trace = volume_tier_charge(rule, usage, period_start)
            charges.append(ExpectedCharge(
                rule_id=rule.rule_id, rule_key=key, description=f"{rule.params['unit_name']} tiered usage",
                amount=amount, math_trace=trace,
                provenance_quote=rule.provenance.quote, provenance_source=rule.source_name,
            ))
            recurring_subtotal += amount
        elif rt == "flat_fee":
            amount, trace = flat_fee_charge(rule, period_start, period_end)
            charges.append(ExpectedCharge(
                rule_id=rule.rule_id, rule_key=key, description="Flat fee",
                amount=amount, math_trace=trace,
                provenance_quote=rule.provenance.quote, provenance_source=rule.source_name,
            ))
            recurring_subtotal += amount

    for key, amount, trace, rule in one_time_charges(effective_rules, period_start, period_end):
        charges.append(ExpectedCharge(
            rule_id=rule.rule_id, rule_key=key, description=rule.params.get("description", "One-time charge"),
            amount=amount, math_trace=trace,
            provenance_quote=rule.provenance.quote, provenance_source=rule.source_name,
        ))

    discount_rule = effective_rules.get("pricing.discount.default")
    if discount_rule is not None and discount_rule.effective_from <= period_start and (
        discount_rule.effective_to is None or discount_rule.effective_to >= period_start
    ):
        if "pct" in discount_rule.params:
            pct = _dec(discount_rule.params["pct"])
            discount_amount = q(recurring_subtotal * pct / Decimal("100"))
            trace = [f"Discount: {pct}% of recurring subtotal {recurring_subtotal} = -{discount_amount}"]
        else:
            discount_amount = q(_dec(discount_rule.params["amount"]))
            trace = [f"Flat discount = -{discount_amount}"]
        charges.append(ExpectedCharge(
            rule_id=discount_rule.rule_id, rule_key="pricing.discount.default", description="Discount",
            amount=-discount_amount, math_trace=trace,
            provenance_quote=discount_rule.provenance.quote, provenance_source=discount_rule.source_name,
        ))

    credit_balance_out = credit_balance_in
    credit_rule = effective_rules.get("pricing.credit.rollover")
    if credit_rule is not None and credit_rule.effective_from <= period_start and (
        credit_rule.effective_to is None or credit_rule.effective_to >= period_start
    ):
        available = credit_balance_in + q(_dec(credit_rule.params["amount"]))
        running_total = sum((c.amount for c in charges), Decimal("0.00"))
        applied = min(available, max(running_total, Decimal("0.00")))
        charges.append(ExpectedCharge(
            rule_id=credit_rule.rule_id, rule_key="pricing.credit.rollover", description="Credit applied",
            amount=-q(applied), math_trace=[f"Credit available {available} (balance {credit_balance_in} + grant "
                                             f"{credit_rule.params['amount']}), applied {q(applied)} against {running_total}"],
            provenance_quote=credit_rule.provenance.quote, provenance_source=credit_rule.source_name,
        ))
        leftover = available - applied
        credit_balance_out = q(leftover) if credit_rule.params.get("rollover", True) else Decimal("0.00")

    invoice = ExpectedInvoice(vendor_id="", period_start=period_start, period_end=period_end, charges=charges)
    return invoice, credit_balance_out
