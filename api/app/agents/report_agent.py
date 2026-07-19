"""Report Agent: violation graph -> executive summary + dispute letters.

Every fact in a dispute letter (clause quote, rule, math trace, dollar
delta) is copied verbatim from a Finding that the deterministic pipeline
already computed. The LLM, when available, is only asked to improve the
prose around those facts -- never to add numbers of its own. The
deterministic template is used verbatim in demo mode and is what every
generated letter is checked against.
"""
from __future__ import annotations

from app.agents.llm_provider import call_llm
from app.pipeline.violation_graph import ViolationGraph
from app.schemas.billing import Finding, Invoice


def executive_summary(graph: ViolationGraph) -> str:
    recovered = graph.total_recovered()
    ranking = graph.vendor_risk_ranking()
    top_clauses = graph.top_clauses_by_loss(3)

    bullets = [f"Total recovered leakage across all vendors: ${recovered:,.2f}."]
    if ranking:
        top = ranking[0]
        bullets.append(f"Highest-risk vendor: {top['vendor_name']} (${top['total_delta']:,.2f} in findings, {top['finding_count']} invoice(s) affected).")
    for c in top_clauses[:2]:
        bullets.append(f"Costliest clause pattern: '{c['rule_key']}' -- ${c['total_delta']:,.2f} across all findings.")

    summary = call_llm(
        "Write a 3-sentence executive summary for a CFO based on these facts, using ONLY the numbers given, "
        "inventing nothing: " + " ".join(bullets),
        system="You are writing for a CFO audience. Be direct, quantify everything, no filler.",
    )
    return summary or " ".join(bullets)


def dispute_letter(finding: Finding, vendor_name: str, invoice: Invoice) -> str:
    math_block = "\n".join(f"  - {line}" for line in finding.math_trace)
    facts = (
        f"Invoice {invoice.invoice_id} (period {invoice.period_start} to {invoice.period_end}): "
        f"billed ${invoice.computed_total:,.2f}, contractually owed ${finding.expected_amount:,.2f}, "
        f"a discrepancy of ${finding.delta:,.2f}. Governing clause ({finding.clause_source}): "
        f"\"{finding.clause_quote}\". Calculation:\n{math_block}"
    )

    letter = call_llm(
        f"Write a formal, professional dispute letter to {vendor_name} using ONLY these facts -- do not invent "
        f"any additional numbers, clauses, or claims: {facts}",
        system="You are drafting a formal vendor billing dispute letter on behalf of the customer.",
    )
    return letter or _template_letter(vendor_name, finding, invoice, math_block)


def _template_letter(vendor_name: str, finding: Finding, invoice: Invoice, math_block: str) -> str:
    return f"""Re: Billing Discrepancy on Invoice {invoice.invoice_id}

To the Billing Department, {vendor_name}:

We are writing to dispute a discrepancy identified on invoice {invoice.invoice_id}, covering the
billing period {invoice.period_start} through {invoice.period_end}.

Per the governing clause ({finding.clause_source}):

    "{finding.clause_quote}"

Our records show the contractually correct charge for this period is ${finding.expected_amount:,.2f}.
The invoice as billed totals ${invoice.computed_total:,.2f}, a discrepancy of ${finding.delta:,.2f}.

Calculation:
{math_block}

We request a corrected invoice or credit memo reflecting the ${finding.delta:,.2f} adjustment within
thirty (30) days. Please contact us with any questions.

Regards,
Accounts Payable
"""
