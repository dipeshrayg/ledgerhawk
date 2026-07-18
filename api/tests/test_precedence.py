"""Precedence resolution across MSA + amendments + an executed email --
the MegaCloud case from the acceptance criteria: the email discount
extension must be honored, with correct provenance.
"""
from datetime import date

from app.pipeline.precedence import effective_rules_dict, resolve_effective_terms
from app.schemas.ast import DocumentRef, DocumentType, Provenance
from app.schemas.dsl import PricingDSL, Rule, RuleType


def rule(rule_key, rule_type, doc_id, source_name, authority_rank, effective_from, effective_to=None, **params):
    return Rule(
        rule_id=f"{doc_id}:{rule_key}",
        rule_key=rule_key,
        rule_type=RuleType(rule_type),
        doc_id=doc_id,
        source_name=source_name,
        authority_rank=authority_rank,
        effective_from=effective_from,
        effective_to=effective_to,
        provenance=Provenance(doc_id=doc_id, section="x", quote=f"quote from {source_name}"),
        params=params,
    )


def test_later_amendment_overrides_msa():
    dsl = PricingDSL(vendor_id="megacloud", rules=[
        rule("pricing.per_unit.seat", "per_unit", "msa", "MSA §6.2", 0, date(2023, 1, 1), rate="15.00", unit_name="seat"),
        rule("pricing.per_unit.seat", "per_unit", "amend2", "Amendment 2 §3", 1, date(2025, 1, 1), rate="18.00", unit_name="seat"),
    ])
    docs = [
        DocumentRef(doc_id="msa", name="MSA", doc_type=DocumentType.MSA, effective_date=date(2023, 1, 1), executed=True, authority_rank=0),
        DocumentRef(doc_id="amend2", name="Amendment 2", doc_type=DocumentType.AMENDMENT, effective_date=date(2025, 1, 1), executed=True, authority_rank=1),
    ]
    effective = effective_rules_dict(dsl, date(2025, 6, 1), docs)
    assert effective["pricing.per_unit.seat"].params["rate"] == "18.00"
    assert effective["pricing.per_unit.seat"].source_name == "Amendment 2 §3"

    # Before the amendment's effective date, the MSA rate still governs.
    effective_early = effective_rules_dict(dsl, date(2024, 6, 1), docs)
    assert effective_early["pricing.per_unit.seat"].params["rate"] == "15.00"


def test_executed_email_extends_discount_over_amendment():
    """MegaCloud precedence case: an amendment sets a discount expiry, but a
    later *executed* email extends it. The email must win, with provenance
    pointing to the email, not the amendment."""
    dsl = PricingDSL(vendor_id="megacloud", rules=[
        rule("pricing.discount.default", "discount", "amend1", "Amendment 1 §2", 1,
             date(2024, 1, 1), date(2024, 12, 31), pct="10"),
        rule("pricing.discount.default", "discount", "email1", "Email Agreement (2025-05-30)", 2,
             date(2025, 1, 1), date(2025, 12, 31), pct="10"),
    ])
    docs = [
        DocumentRef(doc_id="amend1", name="Amendment 1", doc_type=DocumentType.AMENDMENT, effective_date=date(2024, 1, 1), executed=True, authority_rank=1),
        DocumentRef(doc_id="email1", name="Email Agreement", doc_type=DocumentType.EMAIL, effective_date=date(2025, 1, 1), executed=True, authority_rank=2),
    ]
    effective = effective_rules_dict(dsl, date(2025, 6, 1), docs)
    assert effective["pricing.discount.default"].doc_id == "email1"
    assert "Email Agreement" in effective["pricing.discount.default"].source_name


def test_unexecuted_document_never_wins():
    dsl = PricingDSL(vendor_id="vendorx", rules=[
        rule("pricing.per_unit.seat", "per_unit", "msa", "MSA", 0, date(2023, 1, 1), rate="15.00", unit_name="seat"),
        rule("pricing.per_unit.seat", "per_unit", "draft_email", "Unsigned draft email", 5, date(2025, 1, 1), rate="5.00", unit_name="seat"),
    ])
    docs = [
        DocumentRef(doc_id="msa", name="MSA", doc_type=DocumentType.MSA, effective_date=date(2023, 1, 1), executed=True, authority_rank=0),
        DocumentRef(doc_id="draft_email", name="Draft email", doc_type=DocumentType.EMAIL, effective_date=date(2025, 1, 1), executed=False, authority_rank=5),
    ]
    effective = effective_rules_dict(dsl, date(2025, 6, 1), docs)
    assert effective["pricing.per_unit.seat"].params["rate"] == "15.00"


def test_same_day_tiebreak_by_authority_rank():
    dsl = PricingDSL(vendor_id="vendorx", rules=[
        rule("pricing.per_unit.seat", "per_unit", "amend1", "Amendment 1", 1, date(2025, 1, 1), rate="16.00", unit_name="seat"),
        rule("pricing.per_unit.seat", "per_unit", "email1", "Email same-day", 2, date(2025, 1, 1), rate="17.00", unit_name="seat"),
    ])
    docs = [
        DocumentRef(doc_id="amend1", name="Amendment 1", doc_type=DocumentType.AMENDMENT, effective_date=date(2025, 1, 1), executed=True, authority_rank=1),
        DocumentRef(doc_id="email1", name="Email", doc_type=DocumentType.EMAIL, effective_date=date(2025, 1, 1), executed=True, authority_rank=2),
    ]
    effective = effective_rules_dict(dsl, date(2025, 6, 1), docs)
    assert effective["pricing.per_unit.seat"].params["rate"] == "17.00"


def test_superseded_list_tracked_for_provenance():
    dsl = PricingDSL(vendor_id="vendorx", rules=[
        rule("pricing.per_unit.seat", "per_unit", "msa", "MSA", 0, date(2023, 1, 1), rate="15.00", unit_name="seat"),
        rule("pricing.per_unit.seat", "per_unit", "amend1", "Amendment 1", 1, date(2024, 1, 1), rate="16.00", unit_name="seat"),
    ])
    docs = [
        DocumentRef(doc_id="msa", name="MSA", doc_type=DocumentType.MSA, effective_date=date(2023, 1, 1), executed=True, authority_rank=0),
        DocumentRef(doc_id="amend1", name="Amendment 1", doc_type=DocumentType.AMENDMENT, effective_date=date(2024, 1, 1), executed=True, authority_rank=1),
    ]
    resolved = resolve_effective_terms(dsl, date(2025, 1, 1), docs)
    assert resolved["pricing.per_unit.seat"].rule.doc_id == "amend1"
    assert "msa:pricing.per_unit.seat" in resolved["pricing.per_unit.seat"].superseded
