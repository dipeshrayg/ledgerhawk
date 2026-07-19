from decimal import Decimal

from app.pipeline.violation_graph import ViolationGraph
from app.schemas.billing import Finding, Severity


def make_finding(vendor_id, delta, rule_key="pricing.per_unit.seat", invoice_id="inv1"):
    return Finding(
        finding_id=f"f-{vendor_id}-{invoice_id}", vendor_id=vendor_id, invoice_id=invoice_id,
        rule_id="r1", rule_key=rule_key, severity=Severity.HIGH, clause_quote="quote",
        clause_source="MSA", expected_amount=Decimal("100.00"), actual_amount=Decimal("100.00") + delta,
        delta=delta, confidence=1.0, explanation="x", math_trace=[],
    )


def test_total_recovered_sums_only_overcharges():
    g = ViolationGraph([make_finding("v1", Decimal("500.00")), make_finding("v1", Decimal("-50.00"), invoice_id="inv2")])
    assert g.total_recovered() == Decimal("500.00")


def test_vendor_risk_ranking_sorted_desc():
    g = ViolationGraph([
        make_finding("v1", Decimal("200.00")),
        make_finding("v2", Decimal("900.00")),
    ], vendor_names={"v1": "Vendor One", "v2": "Vendor Two"})
    ranking = g.vendor_risk_ranking()
    assert ranking[0]["vendor_id"] == "v2"
    assert ranking[0]["vendor_name"] == "Vendor Two"


def test_top_clauses_by_loss():
    g = ViolationGraph([
        make_finding("v1", Decimal("300.00"), rule_key="pricing.escalation.default"),
        make_finding("v1", Decimal("100.00"), rule_key="pricing.escalation.default", invoice_id="inv2"),
        make_finding("v1", Decimal("50.00"), rule_key="pricing.discount.default", invoice_id="inv3"),
    ])
    top = g.top_clauses_by_loss(1)
    assert top[0]["rule_key"] == "pricing.escalation.default"
    assert top[0]["total_delta"] == Decimal("400.00")


def test_findings_above_threshold():
    g = ViolationGraph([make_finding("v1", Decimal("6000.00")), make_finding("v1", Decimal("10.00"), invoice_id="inv2")])
    assert len(g.findings_above(Decimal("5000"))) == 1
