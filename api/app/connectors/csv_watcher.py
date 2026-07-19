"""CSV drop-folder connector -- watches a directory for new .csv invoice
files and parses them into Invoice objects. Expected columns: vendor_id,
invoice_id, period_start, period_end, invoice_date, line_item_description,
line_item_amount (one row per line item; rows sharing an invoice_id are
grouped into a single Invoice).
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.connectors.base import InvoiceSource
from app.schemas.billing import Invoice, InvoiceLineItem


class CSVDropFolderConnector(InvoiceSource):
    name = "csv_drop_folder"

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()

    def poll(self) -> list[Invoice]:
        new_invoices = []
        for path in sorted(self.folder.glob("*.csv")):
            if path.name in self._seen:
                continue
            self._seen.add(path.name)
            new_invoices.extend(self._parse(path))
        return new_invoices

    def _parse(self, path: Path) -> list[Invoice]:
        rows_by_invoice: dict[str, list[dict]] = {}
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows_by_invoice.setdefault(row["invoice_id"], []).append(row)

        invoices = []
        for invoice_id, rows in rows_by_invoice.items():
            first = rows[0]
            line_items = [InvoiceLineItem(description=r["line_item_description"], amount=Decimal(r["line_item_amount"])) for r in rows]
            invoices.append(Invoice(
                invoice_id=invoice_id, vendor_id=first["vendor_id"],
                period_start=date.fromisoformat(first["period_start"]), period_end=date.fromisoformat(first["period_end"]),
                invoice_date=date.fromisoformat(first["invoice_date"]), line_items=line_items,
                total_amount=sum((li.amount for li in line_items), Decimal("0.00")),
            ))
        return invoices
