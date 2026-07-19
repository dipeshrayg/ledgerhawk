"""Generates ALL seed data + demo-mode fixtures for LedgerHawk.

Single source of truth: this script computes the correct "expected" invoice
for every period via the real precedence resolver + billing engine, then
plants each of the 14 documented discrepancies as an explicit, labeled
mutation of the *actual* invoice relative to that computed baseline. Nothing
here hand-derives a dollar figure -- the engine always computes it, so
docs/DEMO_DATA.md (transcribed from this script's printed summary) and the
e2e test (which reconciles these exact fixtures) can never drift apart.

Run: api/.venv .../python scripts/generate_seed_data.py
"""
from __future__ import annotations

import calendar
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta  # noqa: E402

from app.pipeline import billing_engine, precedence, reconciliation  # noqa: E402
from app.schemas.ast import (  # noqa: E402
    ContractAST,
    ContractTerm,
    DocumentRef,
    DocumentType,
    Party,
    Provenance,
    RenewalType,
)
from app.schemas.billing import Invoice, InvoiceLineItem, UsagePeriod  # noqa: E402
from app.schemas.dsl import PricingDSL, Rule, RuleType  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[1]
DATA = API_ROOT / "data"
FIXTURES = DATA / "fixtures"
VENDORS_TXT = DATA / "vendors"

KIND_MAP = {
    "flat_fee": ("flat_fee", "flat_fee"),
    "per_unit": ("per_unit", "per_unit"),
    "volume_tier": ("volume_tier", "volume_tier"),
    "discount": ("time_bound_discount", "discount"),
    "escalation": ("escalation", "escalation"),
    "one_time": ("one_time_charge", "one_time"),
    "credit": ("credit_rollover", "credit"),
    "proration": ("proration_policy", "proration_policy"),
}


def month_range(start_year, start_month, n):
    periods = []
    y, m = start_year, start_month
    for _ in range(n):
        last_day = calendar.monthrange(y, m)[1]
        periods.append((date(y, m, 1), date(y, m, last_day)))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


PERIODS = month_range(2025, 8, 12)  # Aug 2025 .. Jul 2026, shared across all 5 vendors


def make(kind, rule_key, doc_id, source_name, authority_rank, effective_from, section, quote, params, effective_to=None):
    ast_type, dsl_type = KIND_MAP[kind]
    prov = Provenance(doc_id=doc_id, section=section, quote=quote)
    clause = {
        "clause_id": f"{doc_id}-{section}", "clause_type": ast_type, "rule_key": rule_key, "doc_id": doc_id,
        "effective_from": effective_from, "effective_to": effective_to, "provenance": prov, "params": params,
    }
    rule = Rule(
        rule_id=f"{doc_id}:{rule_key}", rule_key=rule_key, rule_type=RuleType(dsl_type), doc_id=doc_id,
        source_name=source_name, authority_rank=authority_rank, effective_from=effective_from,
        effective_to=effective_to, provenance=prov, params=params,
    )
    return clause, rule


def scenario_total(dsl, docs, period_start, period_end, seats=None, units=None):
    """Computes the correct expected total for a standalone contract-test
    scenario, via the real engine -- never hand-typed. Matches
    app.pipeline.contract_tests_runner.run_scenario: ignores `executed`,
    since a contract test exercises the compiled DSL itself (this must
    work for an unsigned proposal's own contract_tests.yaml, not just
    signed vendors)."""
    usage = UsagePeriod(period_start=period_start, period_end=period_end, seats=seats, units=units or {})
    effective = precedence.effective_rules_dict(dsl, period_start, documents=None)
    invoice, _ = billing_engine.compute_expected_invoice(effective, usage, period_start, period_end)
    return str(invoice.total)


def default_actual(expected):
    return [{"description": c.description, "amount": str(c.amount)} for c in expected.charges]


def mutate_quantity_drift(expected, effective_rules, unit_key, true_qty, phantom_extra, desc):
    rule = effective_rules[unit_key]
    escalation = effective_rules.get("pricing.escalation.default")
    rate, _ = billing_engine.escalated_rate(Decimal(rule.params["rate"]), escalation, expected.period_start)
    wrong_amount = billing_engine.q(rate * (true_qty + phantom_extra))
    items = default_actual(expected)
    for item in items:
        if item["description"] == desc:
            item["amount"] = str(wrong_amount)
    return items, {"true_rate": str(rate), "phantom_units": phantom_extra}


def mutate_full_month_no_proration(expected, effective_rules, unit_key, new_qty, desc):
    rule = effective_rules[unit_key]
    escalation = effective_rules.get("pricing.escalation.default")
    rate, _ = billing_engine.escalated_rate(Decimal(rule.params["rate"]), escalation, expected.period_start)
    wrong_amount = billing_engine.q(rate * new_qty)
    items = default_actual(expected)
    for item in items:
        if item["description"] == desc:
            item["amount"] = str(wrong_amount)
    return items, {"rate": str(rate), "billed_full_month_qty": new_qty}


def mutate_wrong_escalation(expected, effective_rules, unit_key, qty, wrong_years, desc):
    rule = effective_rules[unit_key]
    base_rate = Decimal(rule.params["rate"])
    escalation = effective_rules["pricing.escalation.default"]
    pct = Decimal(escalation.params["pct"])
    wrong_cumulative = pct * wrong_years
    wrong_rate = billing_engine.q(base_rate * (1 + wrong_cumulative / 100))
    wrong_amount = billing_engine.q(wrong_rate * qty)
    items = default_actual(expected)
    for item in items:
        if item["description"] == desc:
            item["amount"] = str(wrong_amount)
    return items, {"wrong_rate": str(wrong_rate), "wrong_cumulative_pct": str(wrong_cumulative)}


def mutate_duplicate_line(expected, desc):
    items = default_actual(expected)
    match = next(dict(i) for i in items if i["description"] == desc)
    items.append(match)
    return items, {"duplicated": desc}


def mutate_remove_line(expected, desc):
    items = default_actual(expected)
    removed = next((i for i in items if i["description"] == desc), None)
    return [i for i in items if i["description"] != desc], {"removed": desc, "removed_amount": removed["amount"] if removed else None}


def mutate_flat_override(expected, desc, wrong_amount):
    items = default_actual(expected)
    for item in items:
        if item["description"] == desc:
            item["amount"] = str(wrong_amount)
    return items, {"billed_amount": str(wrong_amount)}


def build_and_write_vendor(vendor_id, vendor_name, category, ast_kwargs, dsl, docs, usage_periods, mutations, contract_tests):
    """mutations: dict period_index -> (fn, label, kind_description)."""
    ast = ContractAST(contract_id=vendor_id, vendor_name=vendor_name, documents=docs, pricing_clauses=[], **ast_kwargs)

    expected_series = reconciliation.compute_expected_series(dsl, docs, usage_periods)
    invoices = []
    planted = []
    for i, (usage, expected) in enumerate(zip(usage_periods, expected_series)):
        effective_rules = precedence.effective_rules_dict(dsl, usage.period_start, docs)
        if i in mutations:
            fn, label = mutations[i]
            items, meta = fn(expected, effective_rules)
        else:
            items, meta = default_actual(expected), None
        invoice = Invoice(
            invoice_id=f"{vendor_id}-{expected.period_start:%Y%m}",
            vendor_id=vendor_id, period_start=expected.period_start, period_end=expected.period_end,
            invoice_date=expected.period_end + timedelta(days=5),
            line_items=[InvoiceLineItem(**it) for it in items],
            total_amount=sum((Decimal(it["amount"]) for it in items), Decimal("0.00")),
        )
        invoices.append(invoice)
        if i in mutations:
            delta = invoice.computed_total - expected.total
            planted.append({
                "period": f"{expected.period_start:%Y-%m}", "label": mutations[i][1],
                "expected_total": str(expected.total), "actual_total": str(invoice.computed_total),
                "delta": str(delta), "meta": meta,
            })

    results = reconciliation.reconcile_all(dsl, docs, usage_periods, invoices)

    vendor_dir = FIXTURES / vendor_id
    vendor_dir.mkdir(parents=True, exist_ok=True)
    (vendor_dir / "ast.json").write_text(json.dumps(json.loads(ast.model_dump_json()), indent=2))
    (vendor_dir / "dsl.json").write_text(json.dumps(json.loads(dsl.model_dump_json()), indent=2))
    (vendor_dir / "usage.json").write_text(json.dumps([json.loads(u.model_dump_json()) for u in usage_periods], indent=2))
    (vendor_dir / "invoices.json").write_text(json.dumps([json.loads(i.model_dump_json()) for i in invoices], indent=2))
    (vendor_dir / "meta.json").write_text(json.dumps({"vendor_id": vendor_id, "vendor_name": vendor_name, "category": category}, indent=2))
    (vendor_dir / "planted.json").write_text(json.dumps(planted, indent=2))
    (vendor_dir / "contract_tests.yaml").write_text(contract_tests)

    total_recovered = sum((r.findings[0].delta for r in results if r.findings), Decimal("0.00"))
    print(f"\n=== {vendor_name} ({vendor_id}) ===")
    for r in results:
        if r.findings:
            f = r.findings[0]
            print(f"  {r.invoice_id}: FAIL  delta={f.delta:>10}  {f.explanation}")
    print(f"  Findings: {len([r for r in results if r.findings])}  |  Recovered: {total_recovered}")
    return total_recovered, len([r for r in results if r.findings])


# --------------------------------------------------------------------------
# MegaCloud Inc. -- flagship: MSA + 3 amendments + executed email
# --------------------------------------------------------------------------
def build_megacloud():
    vid = "megacloud"
    docs = [
        DocumentRef(doc_id="msa", name="Master Services Agreement", doc_type=DocumentType.MSA,
                    effective_date=date(2022, 1, 1), executed=True, authority_rank=0),
        DocumentRef(doc_id="amend1", name="Amendment 1", doc_type=DocumentType.AMENDMENT,
                    effective_date=date(2024, 1, 1), executed=True, authority_rank=1),
        DocumentRef(doc_id="amend2", name="Amendment 2", doc_type=DocumentType.AMENDMENT,
                    effective_date=date(2025, 1, 1), executed=True, authority_rank=2),
        DocumentRef(doc_id="amend3", name="Amendment 3", doc_type=DocumentType.AMENDMENT,
                    effective_date=date(2025, 7, 1), executed=True, authority_rank=3),
        DocumentRef(doc_id="email1", name="Email Agreement (loyalty discount extension)", doc_type=DocumentType.EMAIL,
                    effective_date=date(2026, 1, 1), executed=True, authority_rank=4),
    ]
    clauses, rules = [], []
    for c, r in [
        make("per_unit", "pricing.per_unit.seat", "msa", "MSA §6.2", 0, date(2022, 1, 1), "6.2",
             "Customer shall pay $15.00 per active seat per month, invoiced monthly in arrears.",
             {"unit_name": "seat", "rate": "15.00"}),
        make("discount", "pricing.discount.default", "amend1", "Amendment 1 §2", 1, date(2024, 1, 1), "2",
             "Customer shall receive a loyalty discount of ten percent (10%) off the recurring subscription fees, "
             "effective January 1, 2024 through December 31, 2024.",
             {"pct": "10"}, effective_to=date(2024, 12, 31)),
        make("per_unit", "pricing.per_unit.seat", "amend2", "Amendment 2 §3", 2, date(2025, 1, 1), "3",
             "Effective January 1, 2025, the per-seat fee set forth in MSA Section 6.2 is amended to $16.50 per "
             "active seat per month.",
             {"unit_name": "seat", "rate": "16.50"}),
        make("escalation", "pricing.escalation.default", "amend2", "Amendment 2 §4", 2, date(2025, 1, 1), "4",
             "Beginning January 1, 2025, fees may increase annually by up to five percent (5%), provided that "
             "cumulative increases under this Section shall not exceed ten percent (10%) above the rate in effect "
             "as of the date of this Amendment.",
             {"pct": "5", "cap_pct": "10", "frequency": "annual"}),
        make("proration", "pricing.proration_policy", "amend2", "Amendment 2 §5", 2, date(2025, 1, 1), "5",
             "Mid-cycle changes in seat count shall be prorated on a daily basis.",
             {"method": "daily"}),
        make("one_time", "pricing.one_time.migration", "amend2", "Amendment 2 §6", 2, date(2025, 1, 1), "6",
             "Customer shall pay a one-time data migration fee of $2,500.00, due upon the September 2025 migration "
             "window.",
             {"amount": "2500.00", "description": "Data migration fee", "date": "2025-09-10"}),
        make("credit", "pricing.credit.rollover", "amend3", "Amendment 3 §2", 3, date(2025, 7, 1), "2",
             "In recognition of the Q2 2025 service incident, Vendor shall issue Customer a monthly service credit "
             "of $200.00, effective July 1, 2025 through June 30, 2026. Any unused credit balance shall roll over "
             "to the following month.",
             {"amount": "200.00", "rollover": True}, effective_to=date(2026, 6, 30)),
        make("discount", "pricing.discount.default", "email1", "Email Agreement (2025-11-15)", 4, date(2026, 1, 1), "1",
             "Confirming that MegaCloud will extend the ten percent (10%) loyalty discount under Amendment 1 "
             "through December 31, 2026, effective January 1, 2026. Please treat this email as an executed "
             "amendment to the Agreement.",
             {"pct": "10"}, effective_to=date(2026, 12, 31)),
    ]:
        clauses.append(c)
        rules.append(r)

    usage = []
    for i, (ps, pe) in enumerate(PERIODS):
        if i < 3:
            usage.append(UsagePeriod(period_start=ps, period_end=pe, seats=11000))
        elif i == 3:
            usage.append(UsagePeriod(period_start=ps, period_end=pe, seats=11000,
                                      seat_change={"date": "2025-11-16", "new_seats": 12800}))
        else:
            usage.append(UsagePeriod(period_start=ps, period_end=pe, seats=12800))

    mutations = {
        0: (lambda e, er: mutate_quantity_drift(e, er, "pricing.per_unit.seat", 11000, 275, "seat usage"),
            "Seat drift: billed for 275 phantom seats above actual provisioned count"),
        1: (lambda e, er: mutate_duplicate_line(e, "Data migration fee"),
            "Double-charged one-time fee: $2,500 migration fee billed twice"),
        3: (lambda e, er: mutate_full_month_no_proration(e, er, "pricing.per_unit.seat", 12800, "seat usage"),
            "Unprorated mid-cycle upgrade: full month billed at new seat count, ignoring daily proration"),
        5: (lambda e, er: mutate_wrong_escalation(e, er, "pricing.per_unit.seat", 12800, 4, "seat usage"),
            "Escalation cap violated: vendor computed escalation from the original 2022 signing date (4 years) "
            "instead of the amendment's 2025 start date (1 year), breaching the 10% cumulative cap"),
        7: (lambda e, er: mutate_remove_line(e, "Credit applied"),
            "Missing rollover credit: $200/mo SLA credit from Amendment 3 not applied"),
        9: (lambda e, er: mutate_remove_line(e, "Discount"),
            "Expired-discount drop: vendor ignored the executed email extending the loyalty discount into 2026"),
    }

    dsl = PricingDSL(vendor_id=vid, rules=rules)
    scenario_amt = scenario_total(dsl, docs, date(2025, 8, 1), date(2025, 8, 31), seats=11000)
    contract_tests = f"""vendor_id: megacloud
tests:
  - name: "11000 seats, steady state, August 2025 -> no discount, no escalation yet"
    type: scenario
    period_start: "2025-08-01"
    period_end: "2025-08-31"
    usage: {{seats: 11000}}
    expect_total: "{scenario_amt}"
  - name: "Escalation cap must never exceed 10%"
    type: invariant
    rule_key: "pricing.escalation.default"
    field: cap_pct
    operator: "<="
    value: "10"
  - name: "Proration policy must be defined"
    type: invariant
    rule_key: "pricing.proration_policy"
    field: method
    operator: "=="
    value: "daily"
"""
    ast_kwargs = dict(
        parties=[Party(name="MegaCloud Inc.", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2022, 1, 1), end_date=date(2027, 1, 1), renewal_type=RenewalType.AUTO,
                          renewal_notice_days=90, auto_renewal_uplift_pct=15.0,
                          provenance=Provenance(doc_id="msa", section="3.1",
                              quote="This Agreement shall automatically renew for successive one-year terms unless "
                                    "either party provides written notice of non-renewal at least ninety (90) days "
                                    "prior to the end of the then-current term.")),
    )
    return build_and_write_vendor(vid, "MegaCloud Inc.", "Cloud & Data Platform", ast_kwargs, dsl, docs, usage, mutations, contract_tests)


# --------------------------------------------------------------------------
# SalesForge CRM -- single MSA
# --------------------------------------------------------------------------
def build_salesforge():
    vid = "salesforge"
    docs = [DocumentRef(doc_id="msa", name="Master Subscription Agreement", doc_type=DocumentType.MSA,
                        effective_date=date(2023, 3, 1), executed=True, authority_rank=0)]
    clauses, rules = [], []
    for c, r in [
        make("per_unit", "pricing.per_unit.user", "msa", "MSA §6.2", 0, date(2023, 3, 1), "6.2",
             "Customer shall pay $15.00 per active user per month.",
             {"unit_name": "user", "rate": "15.00"}),
        make("escalation", "pricing.escalation.default", "msa", "MSA §6.6", 0, date(2026, 3, 1), "6.6",
             "Beginning at each annual renewal starting March 1, 2026, fees may increase by up to five percent "
             "(5%) per year, not to exceed five percent (5%) cumulative above the then-current rate.",
             {"pct": "5", "cap_pct": "5", "frequency": "annual"}),
        make("volume_tier", "pricing.volume.storage_gb", "msa", "MSA §7.1", 0, date(2023, 3, 1), "7.1",
             "Additional data storage is billed at $0.20 per GB for the first 500 GB per month and $0.12 per GB "
             "for each GB thereafter.",
             {"unit_name": "storage_gb", "tiers": [
                 {"min_units": 1, "max_units": 500, "rate": "0.20"},
                 {"min_units": 501, "max_units": None, "rate": "0.12"},
             ]}),
        make("proration", "pricing.proration_policy", "msa", "MSA §6.7", 0, date(2023, 3, 1), "6.7",
             "Mid-cycle changes shall be prorated daily.",
             {"method": "daily"}),
    ]:
        clauses.append(c)
        rules.append(r)

    usage = [UsagePeriod(period_start=ps, period_end=pe, units={"user": 2200, "storage_gb": 800}) for ps, pe in PERIODS]

    mutations = {
        2: (lambda e, er: mutate_flat_override(e, "user usage", str(Decimal("18.00") * 2200)),
            "Per-user rate above contract: billed $18.00/user vs. the contracted $15.00/user (Clause 6.2)"),
        4: (lambda e, er: mutate_flat_override(e, "user usage", str(Decimal("15.75") * 2200)),
            "Price increase before allowed date: 5% escalation applied 3 months before its March 2026 effective date"),
        6: (lambda e, er: mutate_flat_override(e, "storage_gb tiered usage", str(Decimal("800") * Decimal("0.20"))),
            "Subtle volume-tier miscalculation: entire 800GB billed at the first-tier rate instead of graduated pricing"),
    }

    dsl = PricingDSL(vendor_id=vid, rules=rules)
    scenario_amt = scenario_total(dsl, docs, date(2025, 9, 1), date(2025, 9, 30), units={"user": 2200})
    contract_tests = f"""vendor_id: salesforge
tests:
  - name: "2200 users, no escalation active yet (2025) -> flat $15/user"
    type: scenario
    period_start: "2025-09-01"
    period_end: "2025-09-30"
    usage: {{units: {{user: 2200}}}}
    expect_total: "{scenario_amt}"
  - name: "Escalation cap must never exceed 5%"
    type: invariant
    rule_key: "pricing.escalation.default"
    field: cap_pct
    operator: "<="
    value: "5"
"""
    ast_kwargs = dict(
        parties=[Party(name="SalesForge CRM", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2023, 3, 1), end_date=date(2026, 3, 1), renewal_type=RenewalType.AUTO,
                          renewal_notice_days=60,
                          provenance=Provenance(doc_id="msa", section="3.1",
                              quote="This Agreement shall automatically renew for successive one-year terms absent "
                                    "written notice of non-renewal at least sixty (60) days before the end of the "
                                    "then-current term.")),
    )
    return build_and_write_vendor(vid, "SalesForge CRM", "CRM", ast_kwargs, dsl, docs, usage, mutations, contract_tests)


# --------------------------------------------------------------------------
# NimbusPay -- MSA + 1 amendment
# --------------------------------------------------------------------------
def build_nimbuspay():
    vid = "nimbuspay"
    docs = [
        DocumentRef(doc_id="msa", name="Master Services Agreement", doc_type=DocumentType.MSA,
                    effective_date=date(2024, 6, 1), executed=True, authority_rank=0),
        DocumentRef(doc_id="amend1", name="Amendment 1", doc_type=DocumentType.AMENDMENT,
                    effective_date=date(2025, 6, 1), executed=True, authority_rank=1),
    ]
    clauses, rules = [], []
    for c, r in [
        make("per_unit", "pricing.per_unit.employee", "msa", "MSA §5.1", 0, date(2024, 6, 1), "5.1",
             "Customer shall pay $8.00 per active employee per month, processed through the Nimbus payroll "
             "platform.",
             {"unit_name": "employee", "rate": "8.00"}),
        make("flat_fee", "pricing.flat.base", "msa", "MSA §5.2", 0, date(2024, 6, 1), "5.2",
             "In addition to per-employee fees, Customer shall pay a platform base fee of $300.00 per month.",
             {"amount": "300.00", "cadence": "monthly"}),
        make("proration", "pricing.proration_policy", "msa", "MSA §5.4", 0, date(2024, 6, 1), "5.4",
             "Mid-cycle employee count changes shall be prorated daily.",
             {"method": "daily"}),
        make("per_unit", "pricing.per_unit.employee", "amend1", "Amendment 1 §2", 1, date(2025, 6, 1), "2",
             "Effective June 1, 2025, the per-employee fee set forth in MSA Section 5.1 is amended to $8.50 per "
             "active employee per month.",
             {"unit_name": "employee", "rate": "8.50"}),
        make("discount", "pricing.discount.default", "amend1", "Amendment 1 §3", 1, date(2025, 6, 1), "3",
             "Customer shall receive an onboarding discount of fifteen percent (15%) off recurring fees for the "
             "six-month period from June 1, 2025 through November 30, 2025.",
             {"pct": "15"}, effective_to=date(2025, 11, 30)),
        make("one_time", "pricing.one_time.tax_filing", "amend1", "Amendment 1 §4", 1, date(2025, 6, 1), "4",
             "Customer shall pay a one-time year-end tax filing fee of $1,200.00, invoiced in December 2025.",
             {"amount": "1200.00", "description": "Year-end tax filing fee", "date": "2025-12-01"}),
    ]:
        clauses.append(c)
        rules.append(r)

    usage = [UsagePeriod(period_start=ps, period_end=pe, seats=None, units={"employee": 1000}) for ps, pe in PERIODS]

    mutations = {
        5: (lambda e, er: mutate_quantity_drift(e, er, "pricing.per_unit.employee", 1000, 65, "employee usage"),
            "Employee (seat) drift: billed for 1,065 employees vs. 1,000 actually active"),
        4: (lambda e, er: mutate_duplicate_line(e, "Year-end tax filing fee"),
            "Double-charged one-time fee: $1,200 tax filing fee billed twice"),
        11: (lambda e, er: mutate_flat_override(e, "Flat fee", "350.00"),
             "Subtle flat-fee creep: platform base fee billed at $350 vs. contracted $300"),
    }

    dsl = PricingDSL(vendor_id=vid, rules=rules)
    scenario_amt = scenario_total(dsl, docs, date(2026, 2, 1), date(2026, 2, 28), units={"employee": 1000})
    contract_tests = f"""vendor_id: nimbuspay
tests:
  - name: "1000 employees, outside discount window -> base + per-employee"
    type: scenario
    period_start: "2026-02-01"
    period_end: "2026-02-28"
    usage: {{units: {{employee: 1000}}}}
    expect_total: "{scenario_amt}"
  - name: "No escalation clause should exist (fixed-rate contract)"
    type: invariant
    rule_key: "pricing.escalation.default"
    field: pct
    operator: "not_present"
    value: null
"""
    ast_kwargs = dict(
        parties=[Party(name="NimbusPay", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2024, 6, 1), end_date=date(2027, 6, 1), renewal_type=RenewalType.MANUAL,
                          renewal_notice_days=None,
                          provenance=Provenance(doc_id="msa", section="2.1",
                              quote="This Agreement has an initial term of thirty-six (36) months and shall not "
                                    "automatically renew; renewal requires a signed written amendment.")),
    )
    return build_and_write_vendor(vid, "NimbusPay", "Payroll", ast_kwargs, dsl, docs, usage, mutations, contract_tests)


# --------------------------------------------------------------------------
# Crestline Office Supplies -- single MSA, no proration clause (lint bait)
# --------------------------------------------------------------------------
def build_crestline():
    vid = "crestline"
    docs = [DocumentRef(doc_id="msa", name="Supply Services Agreement", doc_type=DocumentType.MSA,
                        effective_date=date(2023, 1, 1), executed=True, authority_rank=0)]
    clauses, rules = [], []
    for c, r in [
        make("flat_fee", "pricing.flat.base", "msa", "MSA §4.1", 0, date(2023, 1, 1), "4.1",
             "Customer shall pay a monthly subscription base fee of $250.00.",
             {"amount": "250.00", "cadence": "monthly"}),
        make("per_unit", "pricing.per_unit.supply_kit", "msa", "MSA §4.2", 0, date(2023, 1, 1), "4.2",
             "Each supply kit ordered shall be billed at $12.00 per kit.",
             {"unit_name": "supply_kit", "rate": "12.00"}),
        make("one_time", "pricing.one_time.admin_fee", "msa", "MSA §4.4", 0, date(2023, 1, 1), "4.4",
             "Customer shall pay an annual contract administration fee of $150.00, invoiced each January.",
             {"amount": "150.00", "description": "Annual contract admin fee", "date": "2026-01-15"}),
    ]:
        clauses.append(c)
        rules.append(r)

    usage = [UsagePeriod(period_start=ps, period_end=pe, seats=None, units={"supply_kit": 90}) for ps, pe in PERIODS]

    mutations = {
        9: (lambda e, er: mutate_flat_override(e, "Flat fee", "300.00"),
            "Flat-fee overcharge: monthly subscription base billed at $300 vs. contracted $250"),
        6: (lambda e, er: mutate_quantity_drift(e, er, "pricing.per_unit.supply_kit", 90, 34, "supply_kit usage"),
            "Usage drift: billed for 124 supply kits vs. 90 actually ordered"),
    }

    dsl = PricingDSL(vendor_id=vid, rules=rules)
    scenario_amt = scenario_total(dsl, docs, date(2025, 9, 1), date(2025, 9, 30), units={"supply_kit": 90})
    contract_tests = f"""vendor_id: crestline
tests:
  - name: "90 kits, base + per-kit, no escalation"
    type: scenario
    period_start: "2025-09-01"
    period_end: "2025-09-30"
    usage: {{units: {{supply_kit: 90}}}}
    expect_total: "{scenario_amt}"
"""
    ast_kwargs = dict(
        parties=[Party(name="Crestline Office Supplies", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2023, 1, 1), end_date=date(2026, 1, 1), renewal_type=RenewalType.AUTO,
                          renewal_notice_days=20,
                          provenance=Provenance(doc_id="msa", section="2.1",
                              quote="This Agreement shall automatically renew annually unless Customer provides "
                                    "written notice of non-renewal at least twenty (20) days before the renewal "
                                    "date.")),
    )
    return build_and_write_vendor(vid, "Crestline Office Supplies", "Office Supplies", ast_kwargs, dsl, docs, usage, mutations, contract_tests)


# --------------------------------------------------------------------------
# PeakServers Hosting -- clean vendor, zero discrepancies
# --------------------------------------------------------------------------
def build_peakservers():
    vid = "peakservers"
    docs = [DocumentRef(doc_id="msa", name="Hosting Services Agreement", doc_type=DocumentType.MSA,
                        effective_date=date(2023, 5, 1), executed=True, authority_rank=0)]
    clauses, rules = [], []
    for c, r in [
        make("per_unit", "pricing.per_unit.server", "msa", "MSA §5.1", 0, date(2023, 5, 1), "5.1",
             "Customer shall pay $40.00 per provisioned server per month.",
             {"unit_name": "server", "rate": "40.00"}),
        make("flat_fee", "pricing.flat.base", "msa", "MSA §5.2", 0, date(2023, 5, 1), "5.2",
             "Customer shall pay a monthly platform base fee of $500.00.",
             {"amount": "500.00", "cadence": "monthly"}),
        make("discount", "pricing.discount.default", "msa", "MSA §5.3", 0, date(2023, 5, 1), "5.3",
             "Customer shall receive a permanent five percent (5%) volume discount off recurring fees.",
             {"pct": "5"}),
        make("proration", "pricing.proration_policy", "msa", "MSA §5.4", 0, date(2023, 5, 1), "5.4",
             "Mid-cycle server count changes shall be prorated daily.",
             {"method": "daily"}),
    ]:
        clauses.append(c)
        rules.append(r)

    usage = [UsagePeriod(period_start=ps, period_end=pe, seats=None, units={"server": 25}) for ps, pe in PERIODS]

    ast_kwargs = dict(
        parties=[Party(name="PeakServers Hosting", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2023, 5, 1), end_date=date(2026, 5, 1), renewal_type=RenewalType.AUTO,
                          renewal_notice_days=60,
                          provenance=Provenance(doc_id="msa", section="2.1",
                              quote="This Agreement shall automatically renew for successive one-year terms unless "
                                    "either party provides written notice of non-renewal at least sixty (60) days "
                                    "prior to the end of the then-current term.")),
    )
    dsl = PricingDSL(vendor_id=vid, rules=rules)
    scenario_amt = scenario_total(dsl, docs, date(2025, 9, 1), date(2025, 9, 30), units={"server": 25})
    contract_tests = f"""vendor_id: peakservers
tests:
  - name: "25 servers, permanent 5% discount"
    type: scenario
    period_start: "2025-09-01"
    period_end: "2025-09-30"
    usage: {{units: {{server: 25}}}}
    expect_total: "{scenario_amt}"
"""
    return build_and_write_vendor(vid, "PeakServers Hosting", "Cloud Hosting", ast_kwargs, dsl, docs, usage, {}, contract_tests)


# --------------------------------------------------------------------------
# TalentBridge HR Suite -- unsigned proposal for F4/F5 Pre-Sign Review.
# Deliberately risky terms: uncapped escalation, quarterly increase cadence,
# short renewal notice. contract_tests.yaml includes one deliberately FAILING
# test (an invariant the proposal's own terms violate).
# --------------------------------------------------------------------------
def build_proposal():
    vid = "talentbridge_proposal"
    docs = [DocumentRef(doc_id="proposal", name="TalentBridge HR Suite -- Proposal", doc_type=DocumentType.PROPOSAL,
                        effective_date=date(2026, 9, 1), executed=False, authority_rank=0)]
    clauses, rules = [], []
    for c, r in [
        make("per_unit", "pricing.per_unit.employee", "proposal", "Proposal §4.1", 0, date(2026, 9, 1), "4.1",
             "Customer shall pay $6.00 per active employee per month.",
             {"unit_name": "employee", "rate": "6.00"}),
        make("escalation", "pricing.escalation.default", "proposal", "Proposal §4.3", 0, date(2026, 9, 1), "4.3",
             "Fees may increase each quarter at Vendor's discretion based on prevailing market rates.",
             {"pct": "8", "frequency": "quarterly"}),
    ]:
        clauses.append(c)
        rules.append(r)

    dsl = PricingDSL(vendor_id=vid, rules=rules)
    ast_kwargs = dict(
        parties=[Party(name="TalentBridge HR Suite", role="vendor"), Party(name="Customer Corp.", role="customer")],
        term=ContractTerm(start_date=date(2026, 9, 1), end_date=date(2027, 9, 1), renewal_type=RenewalType.AUTO,
                          renewal_notice_days=15,
                          provenance=Provenance(doc_id="proposal", section="2.1",
                              quote="This Agreement shall automatically renew for successive one-year terms unless "
                                    "Customer provides written notice of non-renewal at least fifteen (15) days "
                                    "before the end of the then-current term.")),
    )
    ast = ContractAST(contract_id=vid, vendor_name="TalentBridge HR Suite", documents=docs, pricing_clauses=[], **ast_kwargs)

    proposal_dir = DATA / "proposal"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    (proposal_dir / "ast.json").write_text(json.dumps(json.loads(ast.model_dump_json()), indent=2))
    (proposal_dir / "dsl.json").write_text(json.dumps(json.loads(dsl.model_dump_json()), indent=2))
    (proposal_dir / "meta.json").write_text(json.dumps({"vendor_id": vid, "vendor_name": "TalentBridge HR Suite", "category": "HR Suite"}, indent=2))
    (proposal_dir / "contract_tests.yaml").write_text("""vendor_id: talentbridge_proposal
tests:
  - name: "Escalation must be capped (market standard)"
    type: invariant
    rule_key: "pricing.escalation.default"
    field: cap_pct
    operator: "<="
    value: "10"
  - name: "Escalation frequency must be annual, not quarterly"
    type: invariant
    rule_key: "pricing.escalation.default"
    field: frequency
    operator: "=="
    value: "annual"
  - name: "600 employees, September 2026 baseline"
    type: scenario
    period_start: "2026-09-01"
    period_end: "2026-09-30"
    usage: {units: {employee: 600}}
    expect_total: \"""" + scenario_total(dsl, docs, date(2026, 9, 1), date(2026, 9, 30), units={"employee": 600}) + """\"
""")

    proposal_txt_dir = VENDORS_TXT.parent / "proposal"
    proposal_txt_dir.mkdir(parents=True, exist_ok=True)
    (proposal_txt_dir / "proposal.txt").write_text("""TALENTBRIDGE HR SUITE -- COMMERCIAL PROPOSAL (UNSIGNED)

Prepared for: Customer Corp.
Date: September 1, 2026
Status: DRAFT -- not yet executed

1. SERVICES
1.1 Vendor proposes to provide Customer with access to the TalentBridge HR
Suite, covering benefits administration, time tracking, and performance
management.

2. TERM AND RENEWAL
2.1 This Agreement shall automatically renew for successive one-year terms
unless Customer provides written notice of non-renewal at least fifteen
(15) days before the end of the then-current term.

3. CUSTOMER OBLIGATIONS
3.1 Customer shall maintain accurate active-employee counts within the
admin console.

4. FEES AND PAYMENT
4.1 Customer shall pay $6.00 per active employee per month.
4.2 Invoices are issued monthly and due within thirty (30) days.
4.3 Fees may increase each quarter at Vendor's discretion based on
prevailing market rates.

5. LIMITATION OF LIABILITY
5.1 Neither party's aggregate liability under this Agreement shall exceed
the fees paid by Customer in the twelve (12) months preceding the claim.
""")
    print("\n=== TalentBridge HR Suite (proposal, unsigned) ===\n  AST/DSL/contract_tests written -- 2 validator lints + 1 failing contract test expected")


# --------------------------------------------------------------------------
# DataVault Storage v1 -> v2 -- dedicated pair for F6 Version Diff.
# --------------------------------------------------------------------------
def build_diff_pair():
    def make_version(version_suffix, rate, esc_pct, esc_cap, esc_freq, discount_pct, notice_days):
        vid = f"datavault_{version_suffix}"
        doc_id = f"msa_{version_suffix}"
        docs = [DocumentRef(doc_id=doc_id, name=f"DataVault MSA ({version_suffix})", doc_type=DocumentType.MSA,
                            effective_date=date(2025, 1, 1) if version_suffix == "v1" else date(2026, 1, 1),
                            executed=True, authority_rank=0)]
        clauses, rules = [], []
        for c, r in [
            make("per_unit", "pricing.per_unit.tb", doc_id, f"MSA {version_suffix} §5.1", 0, date(2025, 1, 1), "5.1",
                 f"Customer shall pay ${rate}.00 per terabyte stored per month.",
                 {"unit_name": "tb", "rate": f"{rate}.00"}),
            make("escalation", "pricing.escalation.default", doc_id, f"MSA {version_suffix} §5.3", 0, date(2025, 1, 1), "5.3",
                 f"Fees may increase {esc_freq} by up to {esc_pct} percent, not to exceed {esc_cap} percent cumulative.",
                 {"pct": str(esc_pct), "cap_pct": str(esc_cap), "frequency": esc_freq}),
        ]:
            clauses.append(c)
            rules.append(r)
        if discount_pct:
            c, r = make("discount", "pricing.discount.default", doc_id, f"MSA {version_suffix} §5.4", 0, date(2025, 1, 1), "5.4",
                        f"Customer shall receive a {discount_pct} percent discount off recurring fees for the first "
                        "twelve (12) months.",
                        {"pct": str(discount_pct)}, effective_to=date(2025, 12, 31))
            clauses.append(c)
            rules.append(r)
        dsl = PricingDSL(vendor_id=vid, rules=rules)
        ast_kwargs = dict(
            parties=[Party(name="DataVault Storage", role="vendor"), Party(name="Customer Corp.", role="customer")],
            term=ContractTerm(start_date=date(2025, 1, 1), end_date=date(2027, 1, 1), renewal_type=RenewalType.AUTO,
                              renewal_notice_days=notice_days,
                              provenance=Provenance(doc_id=doc_id, section="2.1",
                                  quote=f"This Agreement shall automatically renew for successive one-year terms "
                                        f"unless either party provides written notice of non-renewal at least "
                                        f"{notice_days} days prior to the end of the then-current term.")),
        )
        ast = ContractAST(contract_id=vid, vendor_name="DataVault Storage", documents=docs, pricing_clauses=[], **ast_kwargs)
        return ast, dsl, docs

    ast_v1, dsl_v1, docs_v1 = make_version("v1", rate=20, esc_pct=3, esc_cap=6, esc_freq="annually", discount_pct=5, notice_days=60)
    ast_v2, dsl_v2, docs_v2 = make_version("v2", rate=24, esc_pct=6, esc_cap=15, esc_freq="quarterly", discount_pct=0, notice_days=15)

    diff_dir = DATA / "diff_pair"
    diff_dir.mkdir(parents=True, exist_ok=True)
    for label, ast, dsl in (("v1", ast_v1, dsl_v1), ("v2", ast_v2, dsl_v2)):
        (diff_dir / f"{label}_ast.json").write_text(json.dumps(json.loads(ast.model_dump_json()), indent=2))
        (diff_dir / f"{label}_dsl.json").write_text(json.dumps(json.loads(dsl.model_dump_json()), indent=2))
    (diff_dir / "meta.json").write_text(json.dumps({"vendor_id": "datavault", "vendor_name": "DataVault Storage", "category": "Cloud Hosting"}, indent=2))
    print("\n=== DataVault Storage v1 -> v2 (F6 diff pair) ===\n  rate $20->$24/TB, escalation 3%/6%cap->6%/15%cap quarterly, discount removed, notice 60->15 days")


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    grand_total = Decimal("0.00")
    grand_count = 0
    for builder in (build_megacloud, build_salesforge, build_nimbuspay, build_crestline, build_peakservers):
        total, count = builder()
        grand_total += total
        grand_count += count
    build_proposal()
    build_diff_pair()
    print(f"\n=== GRAND TOTAL ===\nFindings: {grand_count}\nRecovered leakage: {grand_total}")


if __name__ == "__main__":
    main()
