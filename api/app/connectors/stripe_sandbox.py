"""Stripe sandbox connector -- activates only if STRIPE_API_KEY is set.
Illustrative, not hardened: mapping Stripe's invoice object graph to
LedgerHawk's Invoice schema is a roadmap item (see README Limitations).
Included to show the Connector SDK's interface accommodates a real
external billing API, not just file-based sources.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.connectors.base import InvoiceSource
from app.schemas.billing import Invoice


class StripeSandboxConnector(InvoiceSource):
    name = "stripe_sandbox"

    def __init__(self):
        self.enabled = settings.stripe_api_key is not None

    def poll(self) -> list[Invoice]:
        if not self.enabled:
            return []
        try:
            resp = httpx.get(
                "https://api.stripe.com/v1/invoices",
                auth=(settings.stripe_api_key, ""), params={"limit": 10}, timeout=15,
            )
            resp.raise_for_status()
            # Mapping Stripe's invoice shape into ours is a roadmap item --
            # the connector activates and authenticates, but does not yet
            # translate line items into LedgerHawk's DSL-aware Invoice shape.
            return []
        except Exception:
            return []
