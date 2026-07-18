"""Pricing DSL - the executable, lowered form of a Contract AST.

Every rule is plain JSON-serializable data (no code, no eval). The Billing
Engine is the only thing that interprets these rules, and it is 100%
deterministic - see app/pipeline/billing_engine.py. LLMs produce DSL
candidates; they never compute a dollar amount.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.ast import Provenance


class RuleType(str, Enum):
    FLAT_FEE = "flat_fee"
    PER_UNIT = "per_unit"
    VOLUME_TIER = "volume_tier"
    DISCOUNT = "discount"
    ESCALATION = "escalation"
    ONE_TIME = "one_time"
    CREDIT = "credit"
    PRORATION_POLICY = "proration_policy"


class Cadence(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class ProrationMethod(str, Enum):
    DAILY = "daily"          # charge * (days_active / days_in_period)
    NONE = "none"             # full period charged regardless of partial usage
    FULL_MONTH = "full_month"  # any partial month rounds up to a full charge


class VolumeTier(BaseModel):
    min_units: int
    max_units: Optional[int] = None  # None = unbounded top tier
    rate: str  # Decimal-as-string to avoid float drift over the wire


class Rule(BaseModel):
    """One executable pricing rule, lowered from a PricingClause.

    `rule_key` is the precedence-grouping key: among all rules sharing a
    rule_key across MSA/amendments/email, the resolver picks exactly one
    winner as of a given date (see app/pipeline/precedence.py).
    """

    rule_id: str
    rule_key: str
    rule_type: RuleType
    doc_id: str
    source_name: str  # e.g. "Amendment 2" - for provenance display
    authority_rank: int
    effective_from: date
    effective_to: Optional[date] = None
    provenance: Provenance
    params: dict = Field(default_factory=dict)


class PricingDSL(BaseModel):
    vendor_id: str
    rules: list[Rule]


class EffectiveRule(BaseModel):
    """A Rule after precedence resolution, as of a specific date."""

    rule: Rule
    resolved_as_of: date
    superseded: list[str] = Field(default_factory=list)  # rule_ids it beat
