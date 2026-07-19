from datetime import date

from app.agents.negotiation_agent import negotiate
from app.agents.report_agent import dispute_letter, executive_summary
from app.agents.risk_agent import assess
from app.pipeline import loader, reconciliation
from app.pipeline.violation_graph import ViolationGraph


def test_risk_agent_flags_proposal_issues():
    ast, dsl, docs, meta = loader.load_proposal()
    result = assess(ast, dsl)
    codes = {lint["code"] for lint in result["lints"]}
    assert "UNCAPPED_ESCALATION" in codes
    assert "QUARTERLY_ESCALATION" in codes
    assert result["risk_score"] > 0
    assert result["summary"]


def test_negotiation_agent_computes_real_savings_for_risky_proposal():
    ast, dsl, docs, meta = loader.load_proposal()
    benchmarks = loader.load_benchmarks()
    from app.schemas.billing import UsagePeriod
    baseline = UsagePeriod(period_start=date(2026, 9, 1), period_end=date(2026, 9, 1), units={"employee": 600})
    result = negotiate(ast, dsl, meta["category"], benchmarks, baseline, date(2026, 9, 1), months=36)
    assert float(result["expected_savings_36mo"]) > 0
    assert result["negotiation_email"]


def test_report_agent_dispute_letter_cites_real_numbers():
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("megacloud")
    results = reconciliation.reconcile_all(dsl, docs, usage, invoices)
    failing = next(r for r in results if r.findings)
    finding = failing.findings[0]
    invoice = next(i for i in invoices if i.invoice_id == failing.invoice_id)
    letter = dispute_letter(finding, meta["vendor_name"], invoice)
    assert f"{finding.delta:,.2f}" in letter or str(finding.delta) in letter
    assert finding.clause_quote in letter


def test_report_agent_executive_summary_uses_graph_totals():
    all_findings = []
    vendor_names = {}
    for vendor_id, (ast, dsl, docs, usage, invoices, meta) in loader.load_all_vendors().items():
        vendor_names[vendor_id] = meta["vendor_name"]
        results = reconciliation.reconcile_all(dsl, docs, usage, invoices)
        all_findings.extend(r.findings[0] for r in results if r.findings)
    graph = ViolationGraph(all_findings, vendor_names)
    summary = executive_summary(graph)
    assert "86,420.40" in summary or "86420.40" in summary or str(graph.total_recovered()) in summary
