"""Risk Agent: ContractAST + PricingDSL -> risk findings.

The findings themselves (uncapped escalation, short renewal notice,
quarterly-increase clauses, missing proration, conflicting rules) are 100%
deterministic -- app/pipeline/validator.py. This agent's only "AI" job is an
optional plain-English executive annotation on top of those findings; if no
LLM key is configured (or the call fails), a deterministic template summary
is used instead. The risk SCORE is always computed by formula, never by the
LLM, so it can't drift between runs.
"""
from __future__ import annotations

from app.agents.llm_provider import call_llm
from app.pipeline.validator import validate
from app.schemas.ast import ContractAST
from app.schemas.dsl import PricingDSL
from app.schemas.lint import LintSeverity

SEVERITY_WEIGHT = {LintSeverity.HIGH: 30, LintSeverity.MEDIUM: 15, LintSeverity.LOW: 5}


def assess(ast: ContractAST, dsl: PricingDSL) -> dict:
    lints = validate(ast, dsl)
    risk_score = min(100, sum(SEVERITY_WEIGHT[lint.severity] for lint in lints))

    summary = call_llm(
        f"Contract for {ast.vendor_name} has these risk findings: "
        f"{'; '.join(f'[{lint.severity.value}] {lint.message}' for lint in lints) or 'none'}. "
        f"Write a 2-sentence plain-English executive summary of the overall risk.",
        system="You are a contracts risk analyst. Be concise and concrete. Do not invent findings not listed.",
    )
    if not summary:
        summary = _deterministic_summary(ast.vendor_name, lints, risk_score)

    return {
        "vendor_name": ast.vendor_name,
        "risk_score": risk_score,
        "lints": [lint.model_dump(mode="json") for lint in lints],
        "summary": summary,
    }


def _deterministic_summary(vendor_name: str, lints, risk_score: int) -> str:
    if not lints:
        return f"{vendor_name}'s contract has no flagged risk terms. Risk score: {risk_score}/100."
    high = [lint for lint in lints if lint.severity == LintSeverity.HIGH]
    lead = f"{len(high)} high-severity issue(s)" if high else f"{len(lints)} issue(s)"
    return (
        f"{vendor_name}'s contract carries {lead}, most notably: "
        f"{lints[0].message} Risk score: {risk_score}/100."
    )
