from app.pipeline import loader, reconciliation
from app.pipeline.copilot import answer
from app.pipeline.violation_graph import ViolationGraph

QUESTIONS = [
    "Which vendors violated their contracts?",
    "Show overcharges above $5,000",
    "Which clauses caused the most loss?",
    "Why did megacloud's cost jump?",
    "What is our total recovered leakage?",
    "Which vendor has the highest risk?",
    "Show findings for salesforge",
    "What's our compliance rate?",
]


def _build_graph():
    findings, vendor_names, invoice_counts = [], {}, {}
    for vendor_id, (ast, dsl, docs, usage, invoices, meta) in loader.load_all_vendors().items():
        vendor_names[vendor_id] = meta["vendor_name"]
        invoice_counts[vendor_id] = len(invoices)
        results = reconciliation.reconcile_all(dsl, docs, usage, invoices)
        findings.extend(r.findings[0] for r in results if r.findings)
    return ViolationGraph(findings, vendor_names), vendor_names, invoice_counts


def test_all_8_scripted_queries_answer_from_graph_data():
    graph, vendor_names, invoice_counts = _build_graph()
    for q in QUESTIONS:
        result = answer(q, graph, vendor_names, invoice_counts)
        assert result["source"] == "graph", f"Question fell through to fallback: {q!r} -> {result}"
        assert result["answer"]


def test_total_recovered_query_matches_documented_figure():
    graph, vendor_names, invoice_counts = _build_graph()
    result = answer("What is our total recovered leakage?", graph, vendor_names, invoice_counts)
    assert "86,420.40" in result["answer"]


def test_compliance_rate_query():
    graph, vendor_names, invoice_counts = _build_graph()
    result = answer("What's our compliance rate?", graph, vendor_names, invoice_counts)
    assert result["data"]["total"] == 60
    assert result["data"]["passing"] == 46
