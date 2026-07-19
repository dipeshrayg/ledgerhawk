"""Connector SDK (F3) -- the abstract interface every invoice source
implements. A new invoice discovered by `poll()` gets handed straight to
Contract CI (reconcile + contract tests + CI history log), the same as an
upload -- see app/routers/connectors.py. Production connectors for
QuickBooks/NetSuite/SAP are a roadmap item (see README Limitations); this
SDK is what a real one would plug into.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.billing import Invoice


class InvoiceSource(ABC):
    name: str

    @abstractmethod
    def poll(self) -> list[Invoice]:
        """Returns any new invoices discovered since the last poll call."""
        ...
