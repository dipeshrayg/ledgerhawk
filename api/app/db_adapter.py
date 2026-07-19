"""Converts SQLAlchemy rows to the typed Pydantic objects the pipeline
modules operate on. The DB is storage; every computation still runs
through the same AST/DSL/UsagePeriod/Invoice contracts as the tests.
"""
from __future__ import annotations

from app.models_db import InvoiceRow, UsagePeriodRow, Vendor
from app.schemas.ast import ContractAST
from app.schemas.billing import Invoice, InvoiceLineItem, UsagePeriod
from app.schemas.dsl import PricingDSL


def vendor_ast_dsl(vendor: Vendor) -> tuple[ContractAST, PricingDSL]:
    return ContractAST.model_validate(vendor.ast_json), PricingDSL.model_validate(vendor.dsl_json)


def usage_rows_to_pydantic(rows: list[UsagePeriodRow]) -> list[UsagePeriod]:
    return [
        UsagePeriod(period_start=r.period_start, period_end=r.period_end, seats=r.seats,
                    units=r.units_json or {}, seat_change=r.seat_change_json)
        for r in rows
    ]


def invoice_rows_to_pydantic(rows: list[InvoiceRow], vendor_id: str) -> list[Invoice]:
    return [
        Invoice(
            invoice_id=r.invoice_id, vendor_id=vendor_id, period_start=r.period_start, period_end=r.period_end,
            invoice_date=r.invoice_date, line_items=[InvoiceLineItem(**li) for li in r.line_items_json],
            total_amount=r.total_amount,
        )
        for r in rows
    ]
