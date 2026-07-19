# Demo Data - the ground truth ledger

This is the source of truth for the demo. Every number below is computed by
`api/scripts/generate_seed_data.py` from the real Billing Engine and
Precedence Resolver - nothing here is hand-typed arithmetic. Re-run the
script and the numbers will reproduce exactly:

```
cd api && ../.venv/Scripts/python scripts/generate_seed_data.py
```

Invoice window: **August 2025 – July 2026** (12 months, all 5 vendors).

## Headline numbers

| Metric | Value |
|---|---|
| Planted discrepancies | **14** |
| Total recovered leakage | **$86,420.40** |
| Vendors with $0 findings ("doesn't cry wolf") | PeakServers Hosting (12/12 clean invoices) |
| Total invoices reconciled | 60 (5 vendors × 12 months) |
| Clean (PASS) invoices | 46 |
| Failing invoices | 14 |

## Finding-by-finding ledger

### MegaCloud Inc. - flagship (MSA + 3 Amendments + executed email) - 6 findings, $75,885.90

| Month | Type | Expected | Actual | Delta | Explanation |
|---|---|---:|---:|---:|---|
| Aug 2025 | Seat drift | - | - | **$4,537.50** | Billed for 275 phantom seats above the 11,000 actually provisioned (11,275 vs. 11,000 @ $16.50/seat, MSA §6.2 as amended by Amendment 2 §3). |
| Sep 2025 | Double-charged one-time fee | - | - | **$2,500.00** | The $2,500 data migration fee (Amendment 2 §6) was billed twice on the same invoice. |
| Nov 2025 | Unprorated mid-cycle upgrade | - | - | **$14,850.00** | Seats increased 11,000→12,800 on Nov 16. Amendment 2 §5 requires daily proration; the vendor billed the full month at the new count instead. |
| Jan 2026 | Escalation cap violated | - | - | **$31,616.00** | Amendment 2 §4 caps cumulative escalation at 10% from its Jan 2025 start (1 year elapsed → 5%). The vendor instead computed escalation from the original 2022 signing date (4 years → 20%, uncapped), breaching the 10% cap. |
| Mar 2026 | Missing rollover credit | - | - | **$200.00** | The $200/mo SLA service credit from Amendment 3 §2 (Q2 2025 incident credit, rollover-eligible) was not applied. |
| May 2026 | Expired-discount drop | - | - | **$10,051.40** | The Nov 2025 executed email agreement extends the Amendment 1 loyalty discount (10%) through Dec 2026. The vendor's invoice ignored the email and billed full price. **This is the precedence showcase** - see below. |

### SalesForge CRM (single MSA) - 3 findings, $8,274.00

| Month | Type | Delta | Explanation |
|---|---|---:|---|
| Oct 2025 | Per-user rate above contract | **$6,600.00** | Billed $18.00/user × 2,200 users instead of the contracted $15.00/user (MSA §6.2). |
| Dec 2025 | Price increase before allowed date | **$1,650.00** | MSA §6.6 permits a 5% escalation only starting the March 2026 renewal. The vendor applied it three months early. |
| Feb 2026 | Subtle volume-tier miscalculation | **$24.00** | 800GB of storage billed entirely at the first tier's $0.20/GB rate instead of the graduated $0.20/$0.12 split required by MSA §7.1. |

### NimbusPay (MSA + Amendment 1) - 3 findings, $1,802.50

| Month | Type | Delta | Explanation |
|---|---|---:|---|
| Dec 2025 | Double-charged one-time fee | **$1,200.00** | The $1,200 year-end tax filing fee (Amendment 1 §4) billed twice. |
| Jan 2026 | Employee (seat) drift | **$552.50** | Billed for 1,065 employees vs. 1,000 actually active. |
| Jul 2026 | Subtle flat-fee creep | **$50.00** | Platform base fee (MSA §5.2) billed at $350 vs. the contracted $300. |

### Crestline Office Supplies (single MSA) - 2 findings, $458.00

| Month | Type | Delta | Explanation |
|---|---|---:|---|
| Feb 2026 | Usage drift | **$408.00** | Billed for 124 supply kits vs. 90 actually ordered (MSA §4.2, $12/kit). |
| Jun 2026 | Flat-fee overcharge | **$50.00** | Monthly subscription base (MSA §4.1) billed at $300 vs. the contracted $250. |

### PeakServers Hosting - 0 findings (clean vendor)

All 12 invoices PASS exactly. PeakServers has a permanent 5% discount
(MSA §5.3) that is correctly applied every month - proof the tool
recognizes correct discounting instead of flagging every discount as
suspicious. This vendor is the deliberate "doesn't cry wolf" control.

## The MegaCloud precedence case (acceptance criterion)

Documents, in order: **MSA** (2022-01-01) → **Amendment 1** (2024-01-01,
10% discount thru 2024-12-31) → **Amendment 2** (2025-01-01, rate to
$16.50/seat + 5%/yr escalation capped at 10% + daily proration + one-time
migration fee) → **Amendment 3** (2025-07-01, $200/mo rollover SLA credit)
→ **executed email** (sent 2025-11-15, effective 2026-01-01, extends the
10% loyalty discount through Dec 2026).

Querying effective terms as of any date in 2026 correctly returns the
**email's** discount rule (`doc_id: email1`, `source_name: "Email Agreement
(2025-11-15)"`), not Amendment 1's expired one - verified by
`api/tests/test_e2e.py::test_megacloud_precedence_case_email_discount_honored_in_expected_series`
and `api/tests/test_precedence.py`. Rule Inspector (F12) shows this
provenance directly: "from Amendment 2, §3" / "from Email Agreement
(2025-11-15)" next to each effective term.

## Pre-Sign Review fixture: TalentBridge HR Suite (unsigned proposal)

An unsigned proposal (`executed: false`) with deliberately risky terms:
$6.00/employee, and an **uncapped, quarterly** escalation clause ("Fees may
increase each quarter at Vendor's discretion..."). Triggers two Static
Validator lints (`UNCAPPED_ESCALATION`, and frequency is quarterly not
annual) and one deliberately **FAILING** contract test
(`api/data/proposal/contract_tests.yaml`: "Escalation frequency must be
annual, not quarterly" fails against the proposal's quarterly clause).

## Version Diff fixture: DataVault Storage v1 → v2

| Term | v1 | v2 | Change |
|---|---|---|---|
| Per-TB rate | $20.00 | $24.00 | +20% |
| Escalation | 3%/yr, capped 6% | 6%/quarter, capped 15% | frequency 4x, cap +150% |
| First-year discount | 5% | *(removed)* | lost |
| Renewal notice | 60 days | 15 days | -75% |

## Leakage forecast (F2) - MegaCloud, 36 months from Aug 2026

MegaCloud's MSA §3.1 auto-renews annually; the contract carries a 15%
auto-renewal uplift at each renewal (`term.auto_renewal_uplift_pct`),
compounding with the ongoing 5%/yr escalation (capped at 10% cumulative,
Amendment 2 §4). Replaying the compiled DSL forward (no ML - this is
contract replay, holding the current 12,800-seat baseline constant):

```
In 5 months (January 2027), megacloud's cost jumps by $67,494.40/mo --
an estimated $809,932.80/yr impact.
```

Starting monthly cost: **$199,641.60** (Aug 2026) → cost at month 36:
**$353,280.00** (Jul 2029). The jump lands exactly at the Jan 2027 contract
renewal, where the 15% uplift and the escalation clock compound in the same
month - this is the forecast chart's headline driver on the CFO Dashboard
and MegaCloud's vendor-detail forecast view. Reproduce with
`api/tests/test_forecast.py::test_megacloud_forecast_shows_renewal_uplift_jump`.

## Reproducing this exactly

```bash
cd api
../.venv/Scripts/python scripts/generate_seed_data.py   # writes data/fixtures/*, data/proposal/*, data/diff_pair/*
../.venv/Scripts/python scripts/generate_seed_pdfs.py    # renders data/vendors/*/*.pdf from the .txt originals
../.venv/Scripts/python scripts/verify_quotes.py         # asserts every clause quote is verbatim in source text
../.venv/Scripts/python -m pytest tests/test_e2e.py -q   # 14/14 findings, $86,420.40, 0 false positives
```
