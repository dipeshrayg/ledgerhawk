"""Violation Graph - a queryable index over clauses, rules, invoices, and
findings. Nodes are the vendors/invoices/rules/findings already flowing
through the pipeline; edges are the foreign keys already on a Finding
(vendor_id, invoice_id, rule_key). A real graph database would be overkill
for this dataset size, so this is a thin in-memory query layer -- the
Audit Copilot (F10) and CFO Dashboard (F11) are both just callers of it.
"""
from __future__ import annotations

from decimal import Decimal

from app.schemas.billing import Finding


class ViolationGraph:
    def __init__(self, findings: list[Finding], vendor_names: dict[str, str] | None = None):
        self.findings = findings
        self.vendor_names = vendor_names or {}

    def total_recovered(self) -> Decimal:
        return sum((f.delta for f in self.findings if f.delta > 0), Decimal("0.00"))

    def findings_above(self, amount: Decimal) -> list[Finding]:
        return [f for f in self.findings if abs(f.delta) > amount]

    def findings_for_vendor(self, vendor_id: str) -> list[Finding]:
        return [f for f in self.findings if f.vendor_id == vendor_id]

    def vendors_with_violations(self) -> list[str]:
        return sorted({f.vendor_id for f in self.findings})

    def top_clauses_by_loss(self, n: int = 5) -> list[dict]:
        by_key: dict[str, Decimal] = {}
        quotes: dict[str, str] = {}
        for f in self.findings:
            key = f.rule_key or f.clause_quote
            by_key[key] = by_key.get(key, Decimal("0.00")) + f.delta
            quotes[key] = f.clause_quote
        ranked = sorted(by_key.items(), key=lambda kv: abs(kv[1]), reverse=True)[:n]
        return [{"rule_key": k, "total_delta": v, "clause_quote": quotes[k]} for k, v in ranked]

    def vendor_risk_ranking(self) -> list[dict]:
        by_vendor: dict[str, Decimal] = {}
        counts: dict[str, int] = {}
        for f in self.findings:
            by_vendor[f.vendor_id] = by_vendor.get(f.vendor_id, Decimal("0.00")) + f.delta
            counts[f.vendor_id] = counts.get(f.vendor_id, 0) + 1
        ranked = sorted(by_vendor.items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"vendor_id": v, "vendor_name": self.vendor_names.get(v, v), "total_delta": d, "finding_count": counts[v]}
            for v, d in ranked
        ]

    def explain_month_jump(self, vendor_id: str, invoice_id: str) -> Finding | None:
        for f in self.findings:
            if f.vendor_id == vendor_id and f.invoice_id == invoice_id:
                return f
        return None
