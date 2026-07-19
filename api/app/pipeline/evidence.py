"""Evidence Generator - turns an expected/actual invoice diff into a Finding
that traces to a verbatim clause quote, the rule that governs it, and a full
arithmetic explanation. Matching is generic (by line-item description
multiset), not case-specific to any one vendor's discrepancy pattern.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from app.schemas.billing import ExpectedInvoice, Finding, Invoice, Severity


def diff_charges(expected: ExpectedInvoice, actual: Invoice) -> list[dict]:
    """Line-item diff by description. Handles rate/amount changes (matched
    pair, amount differs), duplicated lines (extra actual entries for a
    description), and omitted lines (an expected charge -- e.g. a credit or
    discount -- missing from the actual invoice entirely)."""
    expected_by_desc: dict[str, list] = defaultdict(list)
    for c in expected.charges:
        expected_by_desc[c.description].append(c)
    actual_by_desc: dict[str, list] = defaultdict(list)
    for li in actual.line_items:
        actual_by_desc[li.description].append(li)

    diffs = []
    for desc in set(expected_by_desc) | set(actual_by_desc):
        exp_list = expected_by_desc.get(desc, [])
        act_list = actual_by_desc.get(desc, [])
        rule_ref = exp_list[0] if exp_list else None
        for i in range(max(len(exp_list), len(act_list))):
            exp_amt = exp_list[i].amount if i < len(exp_list) else Decimal("0.00")
            act_amt = act_list[i].amount if i < len(act_list) else Decimal("0.00")
            delta = act_amt - exp_amt
            if delta != 0:
                diffs.append({"description": desc, "expected": exp_amt, "actual": act_amt, "delta": delta, "rule": rule_ref})
    return diffs


def _severity(delta: Decimal) -> Severity:
    magnitude = abs(delta)
    if magnitude > 1000:
        return Severity.HIGH
    if magnitude > 100:
        return Severity.MEDIUM
    return Severity.LOW


def build_finding(vendor_id: str, invoice: Invoice, expected: ExpectedInvoice, diffs: list[dict]) -> Finding | None:
    """One Finding per FAILing invoice, aggregating every line-item diff.
    Returns None if there's nothing to report (a PASSing invoice)."""
    total_delta = sum((d["delta"] for d in diffs), Decimal("0.00"))
    if total_delta == 0:
        return None

    primary = max(diffs, key=lambda d: abs(d["delta"]))
    rule = primary["rule"]
    trace = []
    for d in diffs:
        sign = "overcharge" if d["delta"] > 0 else "undercharge"
        trace.append(
            f"{d['description']}: expected {d['expected']}, billed {d['actual']} "
            f"({sign} of {abs(d['delta'])})"
        )

    return Finding(
        finding_id=str(uuid.uuid4()),
        vendor_id=vendor_id,
        invoice_id=invoice.invoice_id,
        rule_id=rule.rule_id if rule else None,
        rule_key=rule.rule_key if rule else None,
        severity=_severity(total_delta),
        clause_quote=rule.provenance_quote if rule else "(no contractual basis found for this charge)",
        clause_source=rule.provenance_source if rule else "unattributed",
        expected_amount=expected.total,
        actual_amount=invoice.computed_total,
        delta=total_delta,
        confidence=1.0 if rule else 0.75,
        explanation=(
            f"Invoice total is {'higher' if total_delta > 0 else 'lower'} than the contract's "
            f"Virtual Billing Engine replay by {abs(total_delta)}."
        ),
        math_trace=trace,
    )
