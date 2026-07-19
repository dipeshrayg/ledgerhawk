from datetime import date

from app.pipeline.validator import validate
from app.schemas.ast import ContractAST, ContractTerm, DocumentRef, DocumentType, Party, Provenance, RenewalType
from app.schemas.dsl import PricingDSL, Rule, RuleType


def base_ast(renewal_notice_days=None, renewal_type=RenewalType.AUTO):
    return ContractAST(
        contract_id="x", vendor_name="X Inc",
        parties=[Party(name="X Inc", role="vendor"), Party(name="Customer", role="customer")],
        documents=[DocumentRef(doc_id="msa", name="MSA", doc_type=DocumentType.MSA,
                                effective_date=date(2024, 1, 1), executed=True, authority_rank=0)],
        term=ContractTerm(start_date=date(2024, 1, 1), end_date=date(2025, 1, 1),
                          renewal_type=renewal_type, renewal_notice_days=renewal_notice_days,
                          provenance=Provenance(doc_id="msa", section="1", quote="term clause")),
        pricing_clauses=[],
    )


def rule(rule_key, rule_type, **params):
    return Rule(rule_id=rule_key, rule_key=rule_key, rule_type=RuleType(rule_type), doc_id="msa",
                source_name="MSA", authority_rank=0, effective_from=date(2024, 1, 1),
                provenance=Provenance(doc_id="msa", section="1", quote="clause"), params=params)


def test_uncapped_escalation_flagged():
    dsl = PricingDSL(vendor_id="x", rules=[rule("pricing.escalation.default", "escalation", pct="5", frequency="annual")])
    findings = validate(base_ast(), dsl)
    assert any(f.code == "UNCAPPED_ESCALATION" for f in findings)


def test_capped_escalation_not_flagged():
    dsl = PricingDSL(vendor_id="x", rules=[rule("pricing.escalation.default", "escalation", pct="5", cap_pct="10", frequency="annual")])
    findings = validate(base_ast(), dsl)
    assert not any(f.code == "UNCAPPED_ESCALATION" for f in findings)


def test_missing_proration_flagged():
    dsl = PricingDSL(vendor_id="x", rules=[rule("pricing.per_unit.seat", "per_unit", unit_name="seat", rate="10")])
    findings = validate(base_ast(), dsl)
    assert any(f.code == "MISSING_PRORATION_POLICY" for f in findings)


def test_short_renewal_notice_flagged():
    findings = validate(base_ast(renewal_notice_days=10, renewal_type=RenewalType.AUTO), PricingDSL(vendor_id="x", rules=[]))
    assert any(f.code == "SHORT_RENEWAL_NOTICE" for f in findings)


def test_manual_renewal_not_flagged():
    findings = validate(base_ast(renewal_notice_days=None, renewal_type=RenewalType.MANUAL), PricingDSL(vendor_id="x", rules=[]))
    assert not any(f.code == "SHORT_RENEWAL_NOTICE" for f in findings)
