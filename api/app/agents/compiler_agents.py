"""Contract Agent, Pricing Agent, Billing Agent -- typed input/output
contracts per the compiler pipeline (docs/ARCHITECTURE.md).

  Contract Agent  : raw document text            -> ContractAST   (LLM)
  Pricing Agent   : ContractAST pricing clauses   -> PricingDSL    (LLM, validated + retried)
  Billing Agent   : PricingDSL + usage            -> ExpectedInvoice (DETERMINISTIC CODE -- no LLM, ever)

In demo mode (no API key), Contract/Pricing Agents are no-ops: LedgerHawk
ships pre-extracted AST/DSL fixtures for every seeded vendor, so nothing
downstream ever depends on live extraction succeeding. The Billing Agent is
never anything but the plain-Python billing_engine module, regardless of
LLM availability -- this is the "AI can't hallucinate money" guarantee.
"""
from __future__ import annotations

import json

from app.agents.llm_provider import call_llm
from app.config import settings
from app.pipeline import billing_engine, reconciliation  # noqa: F401  (re-exported: the Billing Agent IS this module)
from app.schemas.ast import ContractAST
from app.schemas.dsl import PricingDSL

CONTRACT_EXTRACTION_SYSTEM_PROMPT = """You are a contract extraction agent. Given raw contract text, extract a \
ContractAST JSON object with fields: contract_id, vendor_name, parties, documents, term, pricing_clauses. \
Every pricing_clause and the term MUST carry a `provenance.quote` that is a VERBATIM substring of the input text \
-- never paraphrase. Respond with ONLY the JSON object, no markdown fences, no commentary."""

PRICING_LOWERING_SYSTEM_PROMPT = """You are a pricing lowering agent. Given a ContractAST's pricing_clauses, \
produce a PricingDSL JSON object (a `rules` list) that mirrors each clause's rule_key, effective dates, and \
provenance exactly, translating clause_type to the matching DSL rule_type. Respond with ONLY the JSON object."""


class ExtractionError(Exception):
    """Raised when the Contract/Pricing Agent cannot produce schema-valid
    output after retries -- callers should surface this as 'manual review
    required', never fall back to guessing at numbers."""


def extract_contract_ast(raw_text: str, contract_id: str, max_retries: int = 2) -> ContractAST:
    """Live-LLM path only -- demo-mode vendors never call this (their AST
    ships as a checked-in fixture). Retries on schema validation failure."""
    if settings.is_demo_mode:
        raise ExtractionError("Demo mode has no LLM configured; use app.pipeline.loader fixtures instead.")

    last_error = None
    for _ in range(max_retries):
        raw = call_llm(raw_text, system=CONTRACT_EXTRACTION_SYSTEM_PROMPT)
        if raw is None:
            break
        try:
            return ContractAST.model_validate(json.loads(_strip_fences(raw)))
        except Exception as exc:  # noqa: BLE001 -- retry on ANY malformed output
            last_error = exc
    raise ExtractionError(f"Contract Agent failed to produce a valid ContractAST for {contract_id}: {last_error}")


def lower_to_dsl(ast: ContractAST, max_retries: int = 2) -> PricingDSL:
    if settings.is_demo_mode:
        raise ExtractionError("Demo mode has no LLM configured; use app.pipeline.loader fixtures instead.")

    prompt = json.dumps([c.model_dump(mode="json") for c in ast.pricing_clauses])
    last_error = None
    for _ in range(max_retries):
        raw = call_llm(prompt, system=PRICING_LOWERING_SYSTEM_PROMPT)
        if raw is None:
            break
        try:
            return PricingDSL.model_validate(json.loads(_strip_fences(raw)))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise ExtractionError(f"Pricing Agent failed to produce a valid PricingDSL: {last_error}")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()
