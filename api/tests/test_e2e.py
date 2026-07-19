"""End-to-end acceptance test: reconciling the full seeded dataset must
surface exactly the 14 planted findings, with the exact documented dollar
total, and zero false positives on every clean invoice (including the
entirely clean PeakServers vendor). This is the single test that proves
LedgerHawk's core claim -- see docs/DEMO_DATA.md for the finding-by-finding
ledger this test is checked against.
"""
from decimal import Decimal

from app.pipeline import loader, reconciliation
from app.pipeline.violation_graph import ViolationGraph

EXPECTED_FINDING_COUNT = 14
EXPECTED_TOTAL_RECOVERED = Decimal("86420.40")

EXPECTED_FINDINGS_PER_VENDOR = {
    "megacloud": 6,
    "salesforge": 3,
    "nimbuspay": 3,
    "crestline": 2,
    "peakservers": 0,
}


def run_all_reconciliations():
    all_results = []
    vendor_names = {}
    for vendor_id, (ast, dsl, docs, usage, invoices, meta) in loader.load_all_vendors().items():
        vendor_names[vendor_id] = meta["vendor_name"]
        all_results.extend(reconciliation.reconcile_all(dsl, docs, usage, invoices))
    return all_results, vendor_names


def test_exactly_14_findings_across_all_vendors():
    results, _ = run_all_reconciliations()
    findings = [r.findings[0] for r in results if r.findings]
    assert len(findings) == EXPECTED_FINDING_COUNT


def test_total_recovered_leakage_matches_documented_figure():
    results, _ = run_all_reconciliations()
    findings = [r.findings[0] for r in results if r.findings]
    total = sum((f.delta for f in findings), Decimal("0.00"))
    assert total == EXPECTED_TOTAL_RECOVERED


def test_findings_per_vendor_matches_plan():
    results, _ = run_all_reconciliations()
    for vendor_id, expected_count in EXPECTED_FINDINGS_PER_VENDOR.items():
        vendor_findings = [r for r in results if r.vendor_id == vendor_id and r.findings]
        assert len(vendor_findings) == expected_count, f"{vendor_id}: expected {expected_count}, got {len(vendor_findings)}"


def test_zero_false_positives_on_clean_invoices():
    """Every non-mutated invoice across every vendor -- including ALL 12 of
    PeakServers' -- must PASS. The tool must not cry wolf."""
    results, _ = run_all_reconciliations()
    clean_results = [r for r in results if r.vendor_id == "peakservers"]
    assert len(clean_results) == 12
    assert all(r.status == "PASS" for r in clean_results)
    assert all(r.expected_total == r.actual_total for r in clean_results)

    total_invoices = len(results)
    total_failing = len([r for r in results if r.status == "FAIL"])
    assert total_invoices == 60  # 5 vendors x 12 months
    assert total_failing == EXPECTED_FINDING_COUNT
    assert total_invoices - total_failing == 46  # 46 clean PASSing invoices, zero false positives


def test_every_finding_traces_to_a_verbatim_clause_quote_or_is_explicitly_unattributed():
    results, _ = run_all_reconciliations()
    for r in results:
        for f in r.findings:
            assert f.clause_quote
            assert f.confidence >= 0.75


def test_violation_graph_over_all_findings():
    results, vendor_names = run_all_reconciliations()
    findings = [r.findings[0] for r in results if r.findings]
    graph = ViolationGraph(findings, vendor_names)
    assert graph.total_recovered() == EXPECTED_TOTAL_RECOVERED
    assert "peakservers" not in graph.vendors_with_violations()
    assert "megacloud" in graph.vendors_with_violations()
    ranking = graph.vendor_risk_ranking()
    assert ranking[0]["vendor_id"] == "megacloud"  # largest single-vendor leakage


def test_megacloud_precedence_case_email_discount_honored_in_expected_series():
    """Acceptance criterion: the MegaCloud precedence case resolves
    correctly -- the executed email discount extension is honored in the
    Virtual Billing Engine's expected series for 2026, with provenance
    pointing at the email, not the superseded amendment."""
    from app.pipeline import precedence
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("megacloud")
    effective = precedence.effective_rules_dict(dsl, __import__("datetime").date(2026, 5, 1), docs)
    discount_rule = effective["pricing.discount.default"]
    assert discount_rule.doc_id == "email1"
    assert "Email Agreement" in discount_rule.source_name
