"""Negotiation Agent: findings + benchmarks -> alternative terms, a
negotiation email, a vendor risk score, and an expected-savings figure.

The savings figure is computed, not guessed: it builds a "benchmark-
compliant" copy of the vendor's DSL (escalation capped/annualized to the
category benchmark) and diffs its 36-month forecast against the current
DSL's forecast using the exact same deterministic replay engine that
powers F2. Only the negotiation EMAIL's prose is LLM territory, and it is
instructed to cite the computed numbers, never invent its own.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.agents.llm_provider import call_llm
from app.agents.risk_agent import assess
from app.pipeline.forecast import forecast_series
from app.schemas.ast import ContractAST
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import PricingDSL


def _benchmark_compliant_dsl(dsl: PricingDSL, bench: dict) -> PricingDSL:
    cap = bench.get("escalation_cap_pct_annual")
    new_rules = []
    for r in dsl.rules:
        if r.rule_type.value == "escalation" and cap is not None:
            current_cap = r.params.get("cap_pct")
            needs_cap = current_cap is None or Decimal(str(current_cap)) > Decimal(str(cap))
            needs_freq = r.params.get("frequency") != "annual"
            if needs_cap or needs_freq:
                params = dict(r.params)
                params["cap_pct"] = str(cap) if needs_cap else current_cap
                params["frequency"] = "annual"
                r = r.model_copy(update={"params": params})
        new_rules.append(r)
    return dsl.model_copy(update={"rules": new_rules})


def negotiate(ast: ContractAST, dsl: PricingDSL, category: str, benchmarks: dict, baseline_usage: UsagePeriod, start: date, months: int = 36) -> dict:
    bench = benchmarks.get("categories", {}).get(category, {})
    risk = assess(ast, dsl)

    alt_dsl = _benchmark_compliant_dsl(dsl, bench)
    current_series = forecast_series(ast, dsl, baseline_usage, start, months)
    alt_series = forecast_series(ast, alt_dsl, baseline_usage, start, months)
    current_total = sum((inv.total for inv in current_series), Decimal("0.00"))
    alt_total = sum((inv.total for inv in alt_series), Decimal("0.00"))
    expected_savings = current_total - alt_total

    alt_terms = [
        f"Cap escalation at {bench.get('escalation_cap_pct_annual', 'N/A')}% cumulative, {bench.get('escalation_frequency', 'annual')} cadence "
        f"(market standard for {category})."
    ] if expected_savings > 0 else ["Current terms are already at or better than market benchmark; no changes recommended."]

    email = call_llm(
        f"Draft a professional, firm-but-collaborative negotiation email to {ast.vendor_name} requesting these "
        f"contract changes: {alt_terms}. Cite that our 36-month projected savings from this change is "
        f"${expected_savings:,.2f}. Keep it under 150 words. Do not invent any other numbers.",
        system="You are a procurement negotiator drafting a vendor email. Be direct and professional.",
    )
    if not email:
        email = _template_email(ast.vendor_name, alt_terms, expected_savings)

    return {
        "vendor_name": ast.vendor_name,
        "risk_score": risk["risk_score"],
        "alternative_terms": alt_terms,
        "expected_savings_36mo": str(expected_savings),
        "current_projected_total_36mo": str(current_total),
        "benchmark_projected_total_36mo": str(alt_total),
        "negotiation_email": email,
    }


def _template_email(vendor_name: str, alt_terms: list[str], savings: Decimal) -> str:
    terms_block = "\n".join(f"- {t}" for t in alt_terms)
    return f"""Subject: Contract Terms Review -- {vendor_name}

Hi team,

As part of our regular contract review, we'd like to revisit a few terms
in our agreement to bring them in line with current market standards:

{terms_block}

Based on our projections, this change would save approximately ${savings:,.2f}
over the next 36 months. We value our partnership and would like to
discuss these adjustments at your earliest convenience.

Best regards,
Procurement Team
"""
