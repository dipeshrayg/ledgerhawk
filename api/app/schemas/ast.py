"""Contract AST - typed intermediate representation of a contract's obligations.

Produced by the Contract Agent (LLM) from segmented clause text, or loaded
verbatim from a checked-in fixture in demo mode. Nothing downstream ever
re-reads the source document; everything traces back to a Provenance record
carrying the verbatim clause quote.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    MSA = "MSA"
    AMENDMENT = "AMENDMENT"
    EMAIL = "EMAIL"
    ORDER_FORM = "ORDER_FORM"
    PROPOSAL = "PROPOSAL"


class DocumentRef(BaseModel):
    """One physical/legal document contributing terms to the contract."""

    doc_id: str
    name: str
    doc_type: DocumentType
    effective_date: date
    executed: bool = True  # False = draft/unsigned (e.g. a pending email offer)
    # Explicit authority rank when two documents share an effective_date
    # (e.g. an executed email amendment outranks a same-dated internal memo).
    authority_rank: int = 0


class Provenance(BaseModel):
    """Traces a fact back to the exact document text it was extracted from."""

    doc_id: str
    section: str
    quote: str = Field(description="Verbatim clause text, never paraphrased")
    page: Optional[int] = None


class Party(BaseModel):
    name: str
    role: str  # "vendor" | "customer"


class RenewalType(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"
    NONE = "none"


class ContractTerm(BaseModel):
    start_date: date
    end_date: date
    renewal_type: RenewalType
    renewal_notice_days: Optional[int] = None
    auto_renewal_uplift_pct: Optional[float] = None
    provenance: Provenance


class PricingClauseType(str, Enum):
    FLAT_FEE = "flat_fee"
    PER_UNIT = "per_unit"
    VOLUME_TIER = "volume_tier"
    TIME_BOUND_DISCOUNT = "time_bound_discount"
    ESCALATION = "escalation"
    ONE_TIME_CHARGE = "one_time_charge"
    CREDIT_ROLLOVER = "credit_rollover"
    PRORATION_POLICY = "proration_policy"


class PricingClause(BaseModel):
    """One obligation extracted from contract text, prior to lowering to DSL.

    `rule_key` groups clauses across documents that govern the same
    economic fact (e.g. "pricing.per_unit.seat") so the precedence
    resolver can pick a single winner among MSA/amendment/email variants.
    """

    clause_id: str
    clause_type: PricingClauseType
    rule_key: str
    doc_id: str
    effective_from: date
    effective_to: Optional[date] = None
    provenance: Provenance
    params: dict = Field(default_factory=dict)


class ContractAST(BaseModel):
    contract_id: str
    vendor_name: str
    parties: list[Party]
    documents: list[DocumentRef]
    term: ContractTerm
    pricing_clauses: list[PricingClause]
