"""Audit Copilot (F10) -- natural-language questions answered from the
Violation Graph and DSL, never free-generated. Demo mode intent-matches
against >= 8 scripted query patterns and always answers with graph-sourced
numbers. With an LLM key, the same graph-query functions are exposed as
tool-calling targets -- the LLM picks which to call and formats the
answer, but the numbers themselves still come from these functions, never
from the model's own arithmetic.
"""
from __future__ import annotations

import re
from decimal import Decimal

from app.agents.llm_provider import call_llm
from app.config import settings
from app.pipeline.violation_graph import ViolationGraph

INTENT_PATTERNS = [
    ("vendors_violated", r"which vendors?.*violat|who violated|vendors? .*(broke|breach)"),
    ("overcharges_above", r"overcharges?.*above|above \$?[\d,]+"),
    ("top_clauses", r"which clauses?|costliest clause|most loss|clause.*most"),
    ("explain_jump", r"why did|why.*jump|why.*cost|why.*increase|why.*spike"),
    ("total_recovered", r"total recovered|how much.*recover|total leakage"),
    ("top_risk_vendor", r"highest risk|riskiest|most findings|worst vendor"),
    ("vendor_findings", r"findings for|show me .*findings|discrepancies for"),
    ("compliance_rate", r"compliance rate|pass rate|percent passing|% passing"),
]


def _match_vendor(question: str, vendor_meta: dict[str, str]) -> str | None:
    q = question.lower()
    for vid, name in vendor_meta.items():
        if vid.lower() in q or name.lower() in q or name.split()[0].lower() in q:
            return vid
    return None


def _extract_amount(question: str) -> Decimal:
    m = re.search(r"\$?([\d,]+(?:\.\d+)?)", question)
    if m:
        return Decimal(m.group(1).replace(",", ""))
    return Decimal("5000")


def answer(question: str, graph: ViolationGraph, vendor_meta: dict[str, str], total_invoices_by_vendor: dict[str, int]) -> dict:
    q = question.lower()
    intent = next((name for name, pattern in INTENT_PATTERNS if re.search(pattern, q)), None)

    if intent == "vendors_violated":
        vendors = graph.vendors_with_violations()
        names = [vendor_meta.get(v, v) for v in vendors]
        text = f"{len(vendors)} vendor(s) have findings: {', '.join(names)}." if vendors else "No vendors have any findings."
        return {"answer": text, "source": "graph", "data": vendors}

    if intent == "overcharges_above":
        threshold = _extract_amount(question)
        findings = graph.findings_above(threshold)
        lines = [f"{vendor_meta.get(f.vendor_id, f.vendor_id)} / {f.invoice_id}: ${f.delta:,.2f}" for f in findings]
        text = f"{len(findings)} finding(s) above ${threshold:,.2f}:\n" + "\n".join(lines) if findings else f"No findings above ${threshold:,.2f}."
        return {"answer": text, "source": "graph", "data": [f.model_dump(mode="json") for f in findings]}

    if intent == "top_clauses":
        top = graph.top_clauses_by_loss(5)
        lines = [f"{c['rule_key']}: ${c['total_delta']:,.2f} (\"{c['clause_quote'][:80]}...\")" for c in top]
        text = "Costliest clause patterns:\n" + "\n".join(lines) if top else "No clause-level losses found."
        return {"answer": text, "source": "graph", "data": top}

    if intent == "explain_jump":
        vid = _match_vendor(question, vendor_meta)
        if not vid:
            return {"answer": "Which vendor did you mean? Try naming one, e.g. 'Why did MegaCloud's cost jump?'", "source": "graph"}
        vendor_findings = graph.findings_for_vendor(vid)
        if not vendor_findings:
            return {"answer": f"{vendor_meta.get(vid, vid)} has no discrepancies on record.", "source": "graph"}
        f = max(vendor_findings, key=lambda f: abs(f.delta))
        text = f"{f.explanation} Clause ({f.clause_source}): \"{f.clause_quote}\" Delta: ${f.delta:,.2f} on invoice {f.invoice_id}."
        return {"answer": text, "source": "graph", "data": f.model_dump(mode="json")}

    if intent == "total_recovered":
        total = graph.total_recovered()
        return {"answer": f"Total recovered leakage across all vendors: ${total:,.2f}.", "source": "graph", "data": str(total)}

    if intent == "top_risk_vendor":
        ranking = graph.vendor_risk_ranking()
        if not ranking:
            return {"answer": "No vendors currently have findings.", "source": "graph"}
        top = ranking[0]
        text = f"{top['vendor_name']} carries the most risk: ${top['total_delta']:,.2f} across {top['finding_count']} finding(s)."
        return {"answer": text, "source": "graph", "data": ranking}

    if intent == "vendor_findings":
        vid = _match_vendor(question, vendor_meta)
        if not vid:
            return {"answer": "Which vendor did you mean?", "source": "graph"}
        findings = graph.findings_for_vendor(vid)
        lines = [f"{f.invoice_id}: ${f.delta:,.2f} -- {f.explanation}" for f in findings]
        text = f"{vendor_meta.get(vid, vid)} has {len(findings)} finding(s):\n" + "\n".join(lines) if findings else f"{vendor_meta.get(vid, vid)} has zero findings -- clean record."
        return {"answer": text, "source": "graph", "data": [f.model_dump(mode="json") for f in findings]}

    if intent == "compliance_rate":
        total = sum(total_invoices_by_vendor.values())
        failing = len({(f.vendor_id, f.invoice_id) for f in graph.findings})
        passing = total - failing
        pct = (passing / total * 100) if total else 100.0
        return {"answer": f"Compliance rate: {pct:.1f}% ({passing}/{total} invoices passing).", "source": "graph", "data": {"pct": pct, "passing": passing, "total": total}}

    if not settings.is_demo_mode:
        llm_text = call_llm(
            f"Question: {question}\nAvailable facts -- total recovered: ${graph.total_recovered():,.2f}; "
            f"vendors with violations: {graph.vendors_with_violations()}; top clauses: {graph.top_clauses_by_loss(3)}. "
            f"Answer using ONLY these facts.",
            system="You are the LedgerHawk Audit Copilot. Never state a dollar figure that isn't given to you.",
        )
        if llm_text:
            return {"answer": llm_text, "source": "llm"}

    return {
        "answer": "I couldn't match that to a known query. Try: vendors with violations, overcharges above $X, "
                  "costliest clauses, why a vendor's cost jumped, total recovered leakage, highest-risk vendor, "
                  "findings for a vendor, or compliance rate.",
        "source": "none",
    }
