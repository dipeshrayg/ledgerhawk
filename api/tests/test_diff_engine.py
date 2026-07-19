from datetime import date

from app.pipeline import loader
from app.pipeline.diff_engine import diff_contracts
from app.schemas.billing import UsagePeriod


def test_datavault_v1_v2_diff_categorized_with_dollar_impact():
    (ast_v1, dsl_v1), (ast_v2, dsl_v2) = loader.load_diff_pair()
    baseline = UsagePeriod(period_start=date(2026, 8, 1), period_end=date(2026, 8, 1), units={"tb": 500})
    result = diff_contracts(ast_v1, dsl_v1, ast_v2, dsl_v2, baseline, date(2026, 8, 1), months=36)

    categories = set(result["categories"])
    assert "pricing" in categories
    assert "escalation" in categories
    assert "discount" in categories or "legal_risk" in categories

    rate_change = next(c for c in result["changes"] if c["rule_key"] == "pricing.per_unit.tb")
    assert rate_change["change"] == "modified"
    assert rate_change["v1"]["rate"] == "20.00"
    assert rate_change["v2"]["rate"] == "24.00"

    discount_change = next(c for c in result["changes"] if c["rule_key"] == "pricing.discount.default")
    assert discount_change["change"] == "removed"

    # v2 is strictly more expensive over 36 months (higher rate, faster/uncapped escalation, no discount)
    assert float(result["dollar_impact_36mo"]) > 0


def test_diff_flags_new_legal_risk_from_uncapped_or_short_notice():
    (ast_v1, dsl_v1), (ast_v2, dsl_v2) = loader.load_diff_pair()
    baseline = UsagePeriod(period_start=date(2026, 8, 1), period_end=date(2026, 8, 1), units={"tb": 500})
    result = diff_contracts(ast_v1, dsl_v1, ast_v2, dsl_v2, baseline, date(2026, 8, 1), months=12)
    legal_risk_changes = [c for c in result["changes"] if c["category"] == "legal_risk"]
    assert any(c["rule_key"] == "term.renewal_notice_days" for c in legal_risk_changes)
