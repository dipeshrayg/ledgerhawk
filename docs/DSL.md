# Pricing DSL

The Pricing DSL is the **executable** form of a contract - plain,
JSON-serializable rules with no code and no `eval`. It is what the
deterministic Billing Agent actually runs. See
[`api/app/schemas/dsl.py`](../api/app/schemas/dsl.py) for the Pydantic
source of truth.

## Design law

> LLMs lower AST clauses into DSL *candidates*. The Static Validator checks
> them. The Billing Engine - plain Python, `Decimal` arithmetic, fully
> unit-tested - is the only thing that ever multiplies a rate by a
> quantity. If it isn't in this DSL, it cannot affect a dollar amount.

## Rule shape

```python
class Rule(BaseModel):
    rule_id: str
    rule_key: str          # precedence-grouping key, matches AST clause
    rule_type: RuleType     # flat_fee | per_unit | volume_tier | discount |
                            # escalation | one_time | credit | proration_policy
    doc_id: str
    source_name: str        # "Amendment 2" - for UI provenance
    authority_rank: int
    effective_from: date
    effective_to: date | None
    provenance: Provenance  # verbatim clause quote, inherited from the AST
    params: dict            # rule_type-specific payload, see below
```

## `params` by `rule_type`

| rule_type | params | meaning |
|---|---|---|
| `flat_fee` | `{amount, cadence}` | fixed charge per `monthly`/`annual` period |
| `per_unit` | `{unit_name, rate}` | `rate` × quantity of `unit_name` in the usage record |
| `volume_tier` | `{unit_name, tiers: [{min_units, max_units, rate}]}` | tiered (graduated) per-unit pricing |
| `discount` | `{pct}` or `{amount}` | reduces the computed charge while active |
| `escalation` | `{pct, cap_pct, frequency}` | scheduled rate increase, capped cumulatively |
| `one_time` | `{amount, description, date}` | single non-recurring charge |
| `credit` | `{amount, rollover}` | credit applied to a period; `rollover` carries unused balance forward |
| `proration_policy` | `{method}` | `daily` \| `none` \| `full_month` - how partial periods are billed |

All monetary `params` values are strings (`"15.00"`), converted to
`Decimal` at the engine boundary - never floats, to avoid binary
floating-point drift compounding over 36 months of forecasting.

`volume_tier` tiers are **1-indexed and inclusive**: "the first 1,000 units"
is `{min_units: 1, max_units: 1000}`, and the next tier starts at
`{min_units: 1001, ...}`. Pricing is graduated (each tier only prices the
units that fall inside it), not "highest applicable tier for the whole
quantity." Every line amount is rounded to the cent independently before
being summed - matching how a real invoice presents line items - rather
than summing raw fractional amounts and rounding once at the end.

## Worked example: per-unit + escalation + capped discount

```json
{
  "vendor_id": "megacloud",
  "rules": [
    {
      "rule_id": "r1", "rule_key": "pricing.per_unit.seat",
      "rule_type": "per_unit", "doc_id": "msa", "source_name": "MSA §6.2",
      "authority_rank": 0, "effective_from": "2024-01-01",
      "provenance": {"doc_id": "msa", "section": "6.2",
        "quote": "Customer shall pay $15.00 per active seat per month."},
      "params": {"unit_name": "seat", "rate": "15.00"}
    },
    {
      "rule_id": "r2", "rule_key": "pricing.escalation.default",
      "rule_type": "escalation", "doc_id": "msa", "source_name": "MSA §6.5",
      "authority_rank": 0, "effective_from": "2024-01-01",
      "provenance": {"doc_id": "msa", "section": "6.5",
        "quote": "Fees may increase annually at renewal, not to exceed 5% cumulative."},
      "params": {"pct": "5", "cap_pct": "5", "frequency": "annual"}
    },
    {
      "rule_id": "r3", "rule_key": "pricing.discount.default",
      "rule_type": "discount", "doc_id": "amend1", "source_name": "Amendment 1 §2",
      "authority_rank": 1, "effective_from": "2024-01-01", "effective_to": "2024-12-31",
      "provenance": {"doc_id": "amend1", "section": "2",
        "quote": "A 10% loyalty discount applies through December 31, 2024."},
      "params": {"pct": "10"}
    }
  ]
}
```

Billing engine evaluation for March 2024, 120 seats: `120 × $15.00 = $1,800.00`,
less the active 10% discount = **$1,620.00**. In 2025 the discount has
expired and the escalation has not yet fired (it applies at renewal), so the
same 120 seats bill at the full **$1,800.00** - a jump the Reconciliation
engine will not flag (it's contractual) but the Forecast engine will surface
a year ahead of time.

## Precedence resolution

When multiple documents define rules under the same `rule_key` (MSA base
rate, an amendment override, an executed email extending a discount),
`app/pipeline/precedence.py` resolves the effective rule as of any date `d`:

1. Filter to rules with `effective_from <= d` (and `effective_to` unset or `>= d`).
2. Prefer the rule with the latest `effective_from`.
3. Tie-break by `authority_rank` (higher wins).
4. Unexecuted documents (`executed=False`, e.g. a pending offer) never win.

The result is an `EffectiveRule` carrying the winning `Rule` plus the list of
`rule_id`s it superseded - this is what Rule Inspector (F12) renders as
"Effective terms, with provenance."

## Proration

`proration_policy` rules set how partial periods (a seat added mid-month, a
plan upgraded on the 15th) are billed. `daily` multiplies the period charge
by `days_active / days_in_period`, correctly handling leap-year Februaries
(29-day denominator in leap years). `none` bills the full period regardless.
`full_month` rounds any partial period up to a full charge. See
`api/tests/test_billing_engine.py::test_proration_leap_year` for the
canonical leap-year case.
