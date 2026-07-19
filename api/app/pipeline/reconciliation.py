"""Reconciliation - the F1 core loop. Replays a vendor's DSL chronologically
against real usage to get the expected series (threading credit-rollover
balance across periods), then diffs each period's expected charges against
the actual invoice received, producing a PASS/FAIL ReconciliationResult with
Findings.
"""
from __future__ import annotations

from decimal import Decimal

from app.pipeline import billing_engine, precedence
from app.pipeline.evidence import build_finding, diff_charges
from app.schemas.ast import DocumentRef
from app.schemas.billing import ExpectedInvoice, Invoice, ReconciliationResult, UsagePeriod
from app.schemas.dsl import PricingDSL


def compute_expected_series(
    dsl: PricingDSL, documents: list[DocumentRef], usage_periods: list[UsagePeriod]
) -> list[ExpectedInvoice]:
    balance = Decimal("0.00")
    results = []
    for usage in usage_periods:
        effective = precedence.effective_rules_dict(dsl, usage.period_start, documents)
        inv, balance = billing_engine.compute_expected_invoice(
            effective, usage, usage.period_start, usage.period_end, balance
        )
        inv.vendor_id = dsl.vendor_id
        results.append(inv)
    return results


def reconcile_invoice(vendor_id: str, invoice: Invoice, expected: ExpectedInvoice) -> ReconciliationResult:
    diffs = diff_charges(expected, invoice)
    finding = build_finding(vendor_id, invoice, expected, diffs)
    status = "FAIL" if finding is not None else "PASS"
    return ReconciliationResult(
        vendor_id=vendor_id,
        invoice_id=invoice.invoice_id,
        status=status,
        expected_total=expected.total,
        actual_total=invoice.computed_total,
        findings=[finding] if finding else [],
    )


def reconcile_all(
    dsl: PricingDSL, documents: list[DocumentRef], usage_periods: list[UsagePeriod], invoices: list[Invoice]
) -> list[ReconciliationResult]:
    expected_series = compute_expected_series(dsl, documents, usage_periods)
    expected_by_period = {(e.period_start, e.period_end): e for e in expected_series}
    results = []
    for inv in invoices:
        expected = expected_by_period[(inv.period_start, inv.period_end)]
        results.append(reconcile_invoice(dsl.vendor_id, inv, expected))
    return results
