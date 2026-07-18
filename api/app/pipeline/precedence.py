"""Multi-document precedence resolution.

A vendor's rule set may come from an MSA plus amendments plus an executed
email. This module resolves, per `rule_key` and as of any query date, which
single Rule is in effect - and keeps the provenance chain (which document,
what it beat) so the UI can show "from Amendment 2, §3" next to every
number.

Algorithm (see docs/DSL.md#precedence-resolution):
  1. Only executed documents can win (a draft/pending proposal never
     overrides a signed term).
  2. Among rules for a given rule_key active as of `as_of` (effective_from
     <= as_of <= effective_to-or-open), the one with the latest
     effective_from wins.
  3. Ties on effective_from are broken by authority_rank (higher wins) --
     this is what lets an executed email agreement on the same day as an
     amendment take precedence if it was ranked higher at ingestion.
"""
from __future__ import annotations

from datetime import date

from app.schemas.ast import DocumentRef
from app.schemas.dsl import EffectiveRule, PricingDSL, Rule


def _is_active(rule: Rule, as_of: date) -> bool:
    if rule.effective_from > as_of:
        return False
    if rule.effective_to is not None and rule.effective_to < as_of:
        return False
    return True


def resolve_effective_terms(
    dsl: PricingDSL,
    as_of: date,
    documents: list[DocumentRef] | None = None,
) -> dict[str, EffectiveRule]:
    """Returns the winning Rule per rule_key, as of `as_of`.

    `documents`, if given, filters out rules belonging to unexecuted
    documents (drafts/pending offers never win precedence).
    """
    executed_doc_ids = None
    if documents is not None:
        executed_doc_ids = {d.doc_id for d in documents if d.executed}

    by_key: dict[str, list[Rule]] = {}
    for rule in dsl.rules:
        if executed_doc_ids is not None and rule.doc_id not in executed_doc_ids:
            continue
        if not _is_active(rule, as_of):
            continue
        by_key.setdefault(rule.rule_key, []).append(rule)

    resolved: dict[str, EffectiveRule] = {}
    for key, candidates in by_key.items():
        candidates.sort(key=lambda r: (r.effective_from, r.authority_rank), reverse=True)
        winner = candidates[0]
        superseded = [r.rule_id for r in candidates[1:]]
        resolved[key] = EffectiveRule(rule=winner, resolved_as_of=as_of, superseded=superseded)
    return resolved


def effective_rules_dict(dsl: PricingDSL, as_of: date, documents: list[DocumentRef] | None = None) -> dict[str, Rule]:
    """Convenience: just the winning Rule per key, for feeding into the
    Billing Engine (which doesn't need the superseded-list bookkeeping)."""
    return {k: v.rule for k, v in resolve_effective_terms(dsl, as_of, documents).items()}
