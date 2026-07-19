from datetime import date
from decimal import Decimal

from app.pipeline import loader
from app.pipeline.forecast import forecast_series, leakage_headline, renewal_uplift_multiplier
from app.schemas.ast import ContractTerm, Provenance, RenewalType
from app.schemas.billing import UsagePeriod

FORECAST_START = date(2026, 8, 1)  # the month after the seeded invoice window ends


def test_forecast_series_is_36_months():
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("megacloud")
    baseline = UsagePeriod(period_start=FORECAST_START, period_end=FORECAST_START, seats=12800)
    series = forecast_series(ast, dsl, baseline, FORECAST_START, months=36)
    assert len(series) == 36
    assert series[0].period_start == FORECAST_START


def test_megacloud_forecast_shows_renewal_uplift_jump():
    """MegaCloud's 15% auto-renewal uplift (term.auto_renewal_uplift_pct)
    must show up as the dominant jump in the 36-month forecast -- this is
    the F2 headline the CFO Dashboard surfaces."""
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("megacloud")
    baseline = UsagePeriod(period_start=FORECAST_START, period_end=FORECAST_START, seats=12800)
    result = leakage_headline(ast, dsl, baseline, FORECAST_START, months=36)
    assert result["headline"] is not None
    assert Decimal(result["annualized_impact"]) > Decimal("10000")
    # the jump must land at/after the contract's 2027-01-01 renewal
    jump_date = date.fromisoformat(result["jump_period_start"])
    assert jump_date >= date(2027, 1, 1)


def test_renewal_uplift_compounds_across_successive_renewals():
    term = ContractTerm(start_date=date(2022, 1, 1), end_date=date(2027, 1, 1), renewal_type=RenewalType.AUTO,
                        renewal_notice_days=90, auto_renewal_uplift_pct=15.0,
                        provenance=Provenance(doc_id="msa", section="1", quote="x"))
    assert renewal_uplift_multiplier(term, date(2026, 6, 1)) == Decimal("1")  # before renewal
    m1 = renewal_uplift_multiplier(term, date(2027, 1, 1))
    m2 = renewal_uplift_multiplier(term, date(2028, 1, 1))
    assert m1 == Decimal("1.15")
    assert m2 == Decimal("1.15") ** 2


def test_no_uplift_for_manual_renewal_contracts():
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("nimbuspay")
    assert ast.term.renewal_type == RenewalType.MANUAL
    baseline = UsagePeriod(period_start=FORECAST_START, period_end=FORECAST_START, units={"employee": 1000})
    series = forecast_series(ast, dsl, baseline, FORECAST_START, months=36)
    # fixed-rate contract, no escalation, no renewal uplift -> flat forever
    assert series[0].total == series[-1].total
