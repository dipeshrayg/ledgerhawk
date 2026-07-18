"""Exhaustive tests for the deterministic Billing Engine: tiers, proration
(including leap-year Februaries), escalation caps, and credit rollover.
"""
from datetime import date
from decimal import Decimal

from app.pipeline.billing_engine import compute_expected_invoice
from app.schemas.ast import Provenance
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import Rule, RuleType


def make_rule(rule_key, rule_type, params, effective_from=date(2024, 1, 1), effective_to=None, rule_id=None):
    return Rule(
        rule_id=rule_id or rule_key,
        rule_key=rule_key,
        rule_type=RuleType(rule_type),
        doc_id="msa",
        source_name="MSA",
        authority_rank=0,
        effective_from=effective_from,
        effective_to=effective_to,
        provenance=Provenance(doc_id="msa", section="1", quote="test clause"),
        params=params,
    )


def test_flat_per_unit_charge():
    rules = {"pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "15.00"})}
    usage = UsagePeriod(period_start=date(2024, 3, 1), period_end=date(2024, 3, 31), seats=100)
    invoice, _ = compute_expected_invoice(rules, usage, date(2024, 3, 1), date(2024, 3, 31))
    assert invoice.total == Decimal("1500.00")


def test_volume_tiers_graduated():
    rules = {
        "pricing.volume.api_calls": make_rule(
            "pricing.volume.api_calls", "volume_tier",
            {"unit_name": "api_calls", "tiers": [
                {"min_units": 1, "max_units": 1000, "rate": "0.10"},
                {"min_units": 1001, "max_units": None, "rate": "0.05"},
            ]},
        )
    }
    usage = UsagePeriod(period_start=date(2024, 3, 1), period_end=date(2024, 3, 31), units={"api_calls": 1500})
    invoice, _ = compute_expected_invoice(rules, usage, date(2024, 3, 1), date(2024, 3, 31))
    # First 1000 @ 0.10 = 100.00, remaining 500 @ 0.05 = 25.00 -> 125.00
    assert invoice.total == Decimal("125.00")


def test_proration_daily_mid_month_upgrade():
    rules = {
        "pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "10.00"}),
        "pricing.proration_policy": make_rule("pricing.proration_policy", "proration_policy", {"method": "daily"}),
    }
    # 30-day April: 100 seats for 14 days, 150 seats for 16 days (change on the 15th)
    usage = UsagePeriod(
        period_start=date(2024, 4, 1), period_end=date(2024, 4, 30), seats=100,
        seat_change={"date": "2024-04-15", "new_seats": 150},
    )
    invoice, _ = compute_expected_invoice(rules, usage, date(2024, 4, 1), date(2024, 4, 30))
    expected = Decimal("10.00") * 100 * (Decimal(14) / 30) + Decimal("10.00") * 150 * (Decimal(16) / 30)
    expected = expected.quantize(Decimal("0.01"))
    assert invoice.total == expected


def test_proration_leap_year_february():
    rules = {
        "pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "20.00"}),
        "pricing.proration_policy": make_rule("pricing.proration_policy", "proration_policy", {"method": "daily"}),
    }
    # 2024 is a leap year -> Feb has 29 days. Change on Feb 20 -> 19 days old, 10 days new.
    usage = UsagePeriod(
        period_start=date(2024, 2, 1), period_end=date(2024, 2, 29), seats=50,
        seat_change={"date": "2024-02-20", "new_seats": 80},
    )
    invoice, _ = compute_expected_invoice(rules, usage, date(2024, 2, 1), date(2024, 2, 29))
    # Each segment is rounded to the cent independently (as a real invoice
    # line would be), then summed -- not rounded once after summing.
    part_before = (Decimal("20.00") * 50 * (Decimal(19) / 29)).quantize(Decimal("0.01"))
    part_after = (Decimal("20.00") * 80 * (Decimal(10) / 29)).quantize(Decimal("0.01"))
    assert invoice.total == part_before + part_after
    # sanity: same rule in a non-leap Feb (2023, 28 days) yields a different split
    usage_2023 = UsagePeriod(
        period_start=date(2023, 2, 1), period_end=date(2023, 2, 28), seats=50,
        seat_change={"date": "2023-02-20", "new_seats": 80},
    )
    invoice_2023, _ = compute_expected_invoice(rules, usage_2023, date(2023, 2, 1), date(2023, 2, 28))
    assert invoice_2023.total != invoice.total


def test_escalation_cap_applied():
    rules = {
        "pricing.per_unit.seat": make_rule(
            "pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "15.00"},
            effective_from=date(2022, 1, 1),
        ),
        "pricing.escalation.default": make_rule(
            "pricing.escalation.default", "escalation", {"pct": "5", "cap_pct": "10", "frequency": "annual"},
            effective_from=date(2022, 1, 1),
        ),
    }
    usage = UsagePeriod(period_start=date(2026, 6, 1), period_end=date(2026, 6, 30), seats=100)
    # 4 full years elapsed since 2022-01-01 as of 2026-06 -> 4*5%=20%, capped at 10%.
    invoice, _ = compute_expected_invoice(rules, usage, date(2026, 6, 1), date(2026, 6, 30))
    expected_rate = Decimal("15.00") * Decimal("1.10")
    assert invoice.total == (expected_rate * 100).quantize(Decimal("0.01"))


def test_escalation_uncapped_grows_unbounded():
    rules = {
        "pricing.per_unit.seat": make_rule(
            "pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "15.00"},
            effective_from=date(2020, 1, 1),
        ),
        "pricing.escalation.default": make_rule(
            "pricing.escalation.default", "escalation", {"pct": "5", "frequency": "annual"},
            effective_from=date(2020, 1, 1),
        ),
    }
    usage = UsagePeriod(period_start=date(2030, 1, 1), period_end=date(2030, 1, 31), seats=10)
    invoice, _ = compute_expected_invoice(rules, usage, date(2030, 1, 1), date(2030, 1, 31))
    # 10 years elapsed x 5% = 50% increase, uncapped.
    expected_rate = Decimal("15.00") * Decimal("1.50")
    assert invoice.total == (expected_rate * 10).quantize(Decimal("0.01"))


def test_time_bound_discount_applies_and_expires():
    rules = {
        "pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "10.00"}),
        "pricing.discount.default": make_rule(
            "pricing.discount.default", "discount", {"pct": "10"},
            effective_from=date(2024, 1, 1), effective_to=date(2024, 12, 31),
        ),
    }
    usage = UsagePeriod(period_start=date(2024, 6, 1), period_end=date(2024, 6, 30), seats=100)
    invoice, _ = compute_expected_invoice(rules, usage, date(2024, 6, 1), date(2024, 6, 30))
    assert invoice.total == Decimal("900.00")  # 1000 - 10%

    usage_next_year = UsagePeriod(period_start=date(2025, 6, 1), period_end=date(2025, 6, 30), seats=100)
    invoice_2025, _ = compute_expected_invoice(rules, usage_next_year, date(2025, 6, 1), date(2025, 6, 30))
    assert invoice_2025.total == Decimal("1000.00")  # discount expired


def test_credit_rollover_across_periods():
    rules = {
        "pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "5.00"}),
        "pricing.credit.rollover": make_rule(
            "pricing.credit.rollover", "credit", {"amount": "30.00", "rollover": True},
        ),
    }
    usage = UsagePeriod(period_start=date(2024, 1, 1), period_end=date(2024, 1, 31), seats=4)
    # Month 1: charge 20.00, credit grant 30.00 -> fully offsets, 10.00 rolls over.
    invoice1, balance = compute_expected_invoice(rules, usage, date(2024, 1, 1), date(2024, 1, 31), Decimal("0.00"))
    assert invoice1.total == Decimal("0.00")
    assert balance == Decimal("10.00")

    # Month 2: charge 20.00, credit available = 10 (rollover) + 30 (new grant) = 40 -> fully offsets, 20 rolls over.
    invoice2, balance2 = compute_expected_invoice(rules, usage, date(2024, 2, 1), date(2024, 2, 29), balance)
    assert invoice2.total == Decimal("0.00")
    assert balance2 == Decimal("20.00")


def test_one_time_charge_billed_once_in_correct_period():
    rules = {
        "pricing.per_unit.seat": make_rule("pricing.per_unit.seat", "per_unit", {"unit_name": "seat", "rate": "5.00"}),
        "pricing.one_time.onboarding": make_rule(
            "pricing.one_time.onboarding", "one_time",
            {"amount": "500.00", "description": "Onboarding fee", "date": "2024-01-15"},
        ),
    }
    usage = UsagePeriod(period_start=date(2024, 1, 1), period_end=date(2024, 1, 31), seats=10)
    invoice_jan, _ = compute_expected_invoice(rules, usage, date(2024, 1, 1), date(2024, 1, 31))
    assert invoice_jan.total == Decimal("550.00")

    usage_feb = UsagePeriod(period_start=date(2024, 2, 1), period_end=date(2024, 2, 29), seats=10)
    invoice_feb, _ = compute_expected_invoice(rules, usage_feb, date(2024, 2, 1), date(2024, 2, 29))
    assert invoice_feb.total == Decimal("50.00")  # onboarding fee not repeated
