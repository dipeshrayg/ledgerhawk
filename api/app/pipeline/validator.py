"""Static Validator - schema + semantic lints over a Pricing DSL.

Runs after lowering, before any billing math happens. Each lint has a
severity and a plain-English explanation so a non-engineer (a procurement
or legal reviewer) can act on it directly. This is what powers Pre-Sign
Review (F4) and the risk annotations shown in Rule Inspector (F12).
"""
from __future__ import annotations

from app.schemas.ast import ContractAST, RenewalType
from app.schemas.dsl import PricingDSL
from app.schemas.lint import LintFinding, LintSeverity


def validate(ast: ContractAST, dsl: PricingDSL) -> list[LintFinding]:
    findings: list[LintFinding] = []
    findings += _check_uncapped_escalation(dsl)
    findings += _check_missing_proration_policy(dsl)
    findings += _check_conflicting_rules(dsl)
    findings += _check_auto_renewal_notice(ast)
    findings += _check_quarterly_increase(dsl)
    return findings


def _check_uncapped_escalation(dsl: PricingDSL) -> list[LintFinding]:
    out = []
    for r in dsl.rules:
        if r.rule_type.value == "escalation" and "cap_pct" not in r.params:
            out.append(LintFinding(
                code="UNCAPPED_ESCALATION",
                severity=LintSeverity.HIGH,
                message=f"Escalation clause ({r.source_name}) has no cumulative cap.",
                rule_key=r.rule_key,
                explanation=(
                    "This clause allows fees to increase every period with no ceiling. "
                    "Over a multi-year term this compounds into a large, unbounded cost. "
                    "Market-standard contracts cap cumulative escalation (commonly 5-10%)."
                ),
            ))
    return out


def _check_missing_proration_policy(dsl: PricingDSL) -> list[LintFinding]:
    has_per_unit = any(r.rule_type.value in ("per_unit", "volume_tier") for r in dsl.rules)
    has_policy = any(r.rule_type.value == "proration_policy" for r in dsl.rules)
    if has_per_unit and not has_policy:
        return [LintFinding(
            code="MISSING_PRORATION_POLICY",
            severity=LintSeverity.MEDIUM,
            message="No proration policy found for usage-based pricing.",
            explanation=(
                "The contract prices per-unit or tiered usage but never states how "
                "mid-cycle changes (a seat added on day 15) are billed. Vendors will "
                "default to whatever favors them -- usually full-period billing with "
                "no proration. Silence here is inherently a vendor-favorable term."
            ),
        )]
    return []


def _check_conflicting_rules(dsl: PricingDSL) -> list[LintFinding]:
    out = []
    by_key: dict[str, list] = {}
    for r in dsl.rules:
        by_key.setdefault(r.rule_key, []).append(r)
    for key, rules in by_key.items():
        for i, a in enumerate(rules):
            for b in rules[i + 1:]:
                same_window = (
                    a.effective_from <= (b.effective_to or b.effective_from) and
                    b.effective_from <= (a.effective_to or a.effective_from)
                )
                if same_window and a.authority_rank == b.authority_rank and a.params != b.params:
                    out.append(LintFinding(
                        code="CONFLICTING_RULES",
                        severity=LintSeverity.HIGH,
                        message=f"Two rules for '{key}' overlap in time with equal authority and differing terms "
                                f"({a.source_name} vs {b.source_name}).",
                        rule_key=key,
                        explanation=(
                            "Precedence resolution cannot unambiguously pick a winner here -- both documents "
                            "carry the same authority rank for an overlapping period. This needs a human "
                            "call on which document actually governs."
                        ),
                    ))
    return out


def _check_auto_renewal_notice(ast: ContractAST) -> list[LintFinding]:
    term = ast.term
    if term.renewal_type == RenewalType.AUTO:
        if term.renewal_notice_days is None or term.renewal_notice_days < 30:
            days = term.renewal_notice_days if term.renewal_notice_days is not None else 0
            return [LintFinding(
                code="SHORT_RENEWAL_NOTICE",
                severity=LintSeverity.HIGH,
                message=f"Auto-renewal with only {days}-day notice window.",
                explanation=(
                    "Auto-renewing contracts with a short opt-out window routinely trap customers into "
                    "another full term (often with an uplift) because the cancellation deadline passes "
                    "unnoticed. Market standard is a 60-90 day notice window."
                ),
            )]
    return []


def _check_quarterly_increase(dsl: PricingDSL) -> list[LintFinding]:
    out = []
    for r in dsl.rules:
        if r.rule_type.value == "escalation" and r.params.get("frequency") == "quarterly":
            out.append(LintFinding(
                code="QUARTERLY_ESCALATION",
                severity=LintSeverity.MEDIUM,
                message=f"Escalation clause ({r.source_name}) fires quarterly, not annually.",
                rule_key=r.rule_key,
                explanation=(
                    "Quarterly escalation is far more aggressive than the market-standard annual cadence -- "
                    "it compounds 4x faster over the same period."
                ),
            ))
    return out
