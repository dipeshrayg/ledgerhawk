"""MockERP connector -- simulates a live invoice feed by replaying each
vendor's already-seeded invoice history one period at a time per poll, in
chronological order. Stands in for a real ERP webhook (QuickBooks,
NetSuite, SAP) until one is wired up.
"""
from __future__ import annotations

from app.connectors.base import InvoiceSource
from app.pipeline import loader
from app.schemas.billing import Invoice


class MockERPConnector(InvoiceSource):
    name = "mock_erp"

    def __init__(self, vendor_ids: list[str] | None = None):
        self.vendor_ids = vendor_ids or loader.VENDOR_IDS
        self._queues = {vid: list(loader.load_vendor(vid)[4]) for vid in self.vendor_ids}
        self._cursors = {vid: 0 for vid in self.vendor_ids}

    def poll(self) -> list[Invoice]:
        out = []
        for vid in self.vendor_ids:
            cursor = self._cursors[vid]
            queue = self._queues[vid]
            if cursor < len(queue):
                out.append(queue[cursor])
                self._cursors[vid] += 1
        return out

    def reset(self):
        self._cursors = {vid: 0 for vid in self.vendor_ids}

    def remaining(self) -> int:
        return sum(len(self._queues[vid]) - self._cursors[vid] for vid in self.vendor_ids)
