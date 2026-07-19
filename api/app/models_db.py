"""SQLAlchemy persistence layer.

Deliberately thin: AST/DSL are stored as JSON blobs (they're already
validated, typed Pydantic documents -- re-normalizing every clause into
relational columns would buy nothing but joins). Invoices get real columns
because they're the thing that accumulates over time via connectors (F3)
and is the natural unit of Contract CI history (F9).
"""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    vendor_name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    ast_json: Mapped[dict] = mapped_column(JSON)
    dsl_json: Mapped[dict] = mapped_column(JSON)
    contract_tests_yaml: Mapped[str] = mapped_column(String, default="")

    invoices: Mapped[list["InvoiceRow"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    usage_periods: Mapped[list["UsagePeriodRow"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")


class UsagePeriodRow(Base):
    __tablename__ = "usage_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_pk: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    seats: Mapped[int | None] = mapped_column(nullable=True)
    units_json: Mapped[dict] = mapped_column(JSON, default=dict)
    seat_change_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    vendor: Mapped["Vendor"] = relationship(back_populates="usage_periods")


class InvoiceRow(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_pk: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    invoice_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    invoice_date: Mapped[date] = mapped_column(Date)
    line_items_json: Mapped[list] = mapped_column(JSON)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    source: Mapped[str] = mapped_column(String, default="seed")  # seed | upload | mockerp | csv | stripe
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    vendor: Mapped["Vendor"] = relationship(back_populates="invoices")


class CIRun(Base):
    """One Contract CI build result -- reconciliation + contract tests for
    a single invoice event (F9)."""
    __tablename__ = "ci_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String, index=True)
    invoice_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # PASS | FAIL
    expected_total: Mapped[float] = mapped_column(Numeric(12, 2))
    actual_total: Mapped[float] = mapped_column(Numeric(12, 2))
    delta: Mapped[float] = mapped_column(Numeric(12, 2))
    contract_tests_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ProposalRow(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, unique=True)
    vendor_name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    ast_json: Mapped[dict] = mapped_column(JSON)
    dsl_json: Mapped[dict] = mapped_column(JSON)
    contract_tests_yaml: Mapped[str] = mapped_column(String, default="")


class DiffPairRow(Base):
    __tablename__ = "diff_pairs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pair_id: Mapped[str] = mapped_column(String, unique=True)
    vendor_name: Mapped[str] = mapped_column(String)
    v1_ast_json: Mapped[dict] = mapped_column(JSON)
    v1_dsl_json: Mapped[dict] = mapped_column(JSON)
    v2_ast_json: Mapped[dict] = mapped_column(JSON)
    v2_dsl_json: Mapped[dict] = mapped_column(JSON)
