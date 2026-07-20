#!/usr/bin/env python
"""Contract CI CLI -- reconciles a single invoice JSON file against a
vendor's compiled contract and exits non-zero on FAIL. This is what
examples/github-actions-contract-ci.yml runs on every invoice commit.

Usage:
    python reconcile_cli.py <vendor_id> <invoice.json>

Invoice JSON shape:
    {"invoice_id": "...", "period_start": "YYYY-MM-DD", "period_end": "YYYY-MM-DD",
     "invoice_date": "YYYY-MM-DD", "line_items": [{"description": "...", "amount": "123.45"}]}
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import loader, reconciliation  # noqa: E402
from app.schemas.billing import Invoice, InvoiceLineItem  # noqa: E402


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    vendor_id, invoice_path = sys.argv[1], sys.argv[2]

    ast, dsl, docs, usage, _existing_invoices, meta = loader.load_vendor(vendor_id)
    raw = json.loads(Path(invoice_path).read_text())
    line_items = [InvoiceLineItem(**li) for li in raw["line_items"]]
    invoice = Invoice(
        invoice_id=raw["invoice_id"], vendor_id=vendor_id,
        period_start=raw["period_start"], period_end=raw["period_end"], invoice_date=raw["invoice_date"],
        line_items=line_items, total_amount=sum((Decimal(li.amount) for li in line_items), Decimal("0.00")),
    )

    expected_series = reconciliation.compute_expected_series(dsl, docs, usage)
    expected = next((e for e in expected_series if e.period_start == invoice.period_start), None)
    if expected is None:
        print(f"No usage baseline for period {invoice.period_start} -- cannot reconcile.")
        sys.exit(2)

    result = reconciliation.reconcile_invoice(vendor_id, invoice, expected)
    print(f"[{meta['vendor_name']}] {invoice.invoice_id}: {result.status}  "
          f"expected=${result.expected_total}  billed=${result.actual_total}")
    if result.findings:
        f = result.findings[0]
        print(f"  FINDING: {f.explanation}")
        print(f'  Clause ({f.clause_source}): "{f.clause_quote}"')
        print(f"  Delta: ${f.delta}")

    sys.exit(1 if result.status == "FAIL" else 0)


if __name__ == "__main__":
    main()
