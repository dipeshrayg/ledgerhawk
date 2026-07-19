"""Contract Version Diff (F6) -- "git diff for contracts." Diffs two
compiled contracts (AST term + DSL rules) at the rule level, categorizes
each change, and estimates the 36-month dollar impact by replaying both
versions through the same deterministic forecast engine used for F2.
"""
from __future__ import annotations

from decimal import Decimal

from app.pipeline.forecast import forecast_series
from app.pipeline.validator import validate


def _category(rule_key: str, rule_type: str) -> str:
    if "escalation" in rule_key:
        return "escalation"
    if "discount" in rule_key:
        return "discount"
    if "credit" in rule_key:
        return "credit"
    if rule_type in ("per_unit", "volume_tier", "flat_fee", "one_time"):
        return "pricing"
    return "other"


def _explain(rule_type: str, key: str, p1: dict, p2: dict) -> str:
    if rule_type == "per_unit":
        return f"Per-unit rate changed from ${p1['rate']} to ${p2['rate']} per {p1.get('unit_name', 'unit')}."
    if rule_type == "escalation":
        parts = []
        if p1.get("cap_pct") != p2.get("cap_pct"):
            parts.append(f"cap {p1.get('cap_pct', 'uncapped')}% -> {p2.get('cap_pct', 'uncapped')}%")
        if p1.get("pct") != p2.get("pct"):
            parts.append(f"rate {p1.get('pct')}% -> {p2.get('pct')}%")
        if p1.get("frequency") != p2.get("frequency"):
            parts.append(f"frequency {p1.get('frequency')} -> {p2.get('frequency')}")
        return "Escalation clause changed: " + (", ".join(parts) if parts else "terms changed") + "."
    if rule_type == "discount":
        return f"Discount changed from {p1} to {p2}."
    return f"{key} changed from {p1} to {p2}."


def diff_rules(dsl_v1, dsl_v2) -> list[dict]:
    rules_v1 = {r.rule_key: r for r in dsl_v1.rules}
    rules_v2 = {r.rule_key: r for r in dsl_v2.rules}
    keys = sorted(set(rules_v1) | set(rules_v2))
    changes = []
    for key in keys:
        r1, r2 = rules_v1.get(key), rules_v2.get(key)
        if r1 and not r2:
            changes.append({"rule_key": key, "category": _category(key, r1.rule_type.value), "change": "removed",
                            "v1": r1.params, "v2": None, "explanation": f"'{key}' was removed in v2 ({r1.provenance.quote})."})
        elif r2 and not r1:
            changes.append({"rule_key": key, "category": _category(key, r2.rule_type.value), "change": "added",
                            "v1": None, "v2": r2.params, "explanation": f"'{key}' is new in v2 ({r2.provenance.quote})."})
        elif r1.params != r2.params:
            changes.append({"rule_key": key, "category": _category(key, r1.rule_type.value), "change": "modified",
                            "v1": r1.params, "v2": r2.params, "explanation": _explain(r1.rule_type.value, key, r1.params, r2.params)})
    return changes


def diff_legal_risk(ast_v1, dsl_v1, ast_v2, dsl_v2) -> list[dict]:
    lints_v1 = {lint.code for lint in validate(ast_v1, dsl_v1)}
    lints_v2 = validate(ast_v2, dsl_v2)
    new_lints = [lint for lint in lints_v2 if lint.code not in lints_v1]
    out = [{"rule_key": lint.rule_key, "category": "legal_risk", "change": "new_risk",
            "v1": None, "v2": lint.code, "explanation": f"{lint.message} {lint.explanation}"} for lint in new_lints]
    if ast_v1.term.renewal_notice_days != ast_v2.term.renewal_notice_days:
        out.append({"rule_key": "term.renewal_notice_days", "category": "legal_risk", "change": "modified",
                    "v1": ast_v1.term.renewal_notice_days, "v2": ast_v2.term.renewal_notice_days,
                    "explanation": f"Renewal notice window changed from {ast_v1.term.renewal_notice_days} to "
                                   f"{ast_v2.term.renewal_notice_days} days."})
    return out


def diff_contracts(ast_v1, dsl_v1, ast_v2, dsl_v2, baseline_usage, start, months: int = 36) -> dict:
    changes = diff_rules(dsl_v1, dsl_v2) + diff_legal_risk(ast_v1, dsl_v1, ast_v2, dsl_v2)

    series_v1 = forecast_series(ast_v1, dsl_v1, baseline_usage, start, months)
    series_v2 = forecast_series(ast_v2, dsl_v2, baseline_usage, start, months)
    total_v1 = sum((inv.total for inv in series_v1), Decimal("0.00"))
    total_v2 = sum((inv.total for inv in series_v2), Decimal("0.00"))

    return {
        "changes": changes,
        "total_v1_36mo": str(total_v1),
        "total_v2_36mo": str(total_v2),
        "dollar_impact_36mo": str(total_v2 - total_v1),
        "categories": sorted({c["category"] for c in changes}),
    }
