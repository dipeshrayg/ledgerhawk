"""Usage, invoice, and finding schemas - the data the Billing Engine consumes
and the evidence it produces.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class UsagePeriod(BaseModel):
    """Actual usage/consumption for one billing period, as reported by the
    customer's own systems (seats provisioned, units consumed, etc.) - this
    is ground truth the vendor is contractually bound to price against.
    """

    period_start: date
    period_end: date
    seats: Optional[int] = None
    units: dict[str, int] = Field(default_factory=dict)  # e.g. {"api_calls": 12000}
    one_time_charges: list[dict] = Field(default_factory=list)  # [{desc, amount, date}]
    # Mid-period change, e.g. a seat upgrade on the 15th - exercises proration.
    seat_change: Optional[dict] = None  # {"date": "YYYY-MM-DD", "new_seats": int}


class InvoiceLineItem(BaseModel):
    description: str
    amount: Decimal


class Invoice(BaseModel):
    invoice_id: str
    vendor_id: str
    period_start: date
    period_end: date
    invoice_date: date
    line_items: list[InvoiceLineItem]
    total_amount: Decimal

    @property
    def computed_total(self) -> Decimal:
        return sum((li.amount for li in self.line_items), Decimal("0"))


class ExpectedCharge(BaseModel):
    """One line of the Virtual Billing Engine's expected-charge output."""

    rule_id: str
    rule_key: str
    description: str
    amount: Decimal
    math_trace: list[str]
    provenance_quote: str
    provenance_source: str


class ExpectedInvoice(BaseModel):
    vendor_id: str
    period_start: date
    period_end: date
    charges: list[ExpectedCharge]

    @property
    def total(self) -> Decimal:
        return sum((c.amount for c in self.charges), Decimal("0"))


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Finding(BaseModel):
    """One overcharge/undercharge finding - a 'failing test' in CI-for-
    contracts framing. Every field is traceable: no number here is ever
    LLM-generated.
    """

    finding_id: str
    vendor_id: str
    invoice_id: str
    rule_id: Optional[str] = None
    rule_key: Optional[str] = None
    severity: Severity
    clause_quote: str
    clause_source: str
    expected_amount: Decimal
    actual_amount: Decimal
    delta: Decimal  # actual - expected (positive = overcharge)
    confidence: float
    explanation: str
    math_trace: list[str]


class ReconciliationResult(BaseModel):
    vendor_id: str
    invoice_id: str
    status: str  # "PASS" | "FAIL"
    expected_total: Decimal
    actual_total: Decimal
    findings: list[Finding]
