"""Loads checked-in demo-mode fixtures (pre-extracted AST/DSL + usage +
invoices) from disk. This is what "zero-key demo mode" means in practice --
the same ContractAST/PricingDSL/Invoice objects a live LLM extraction would
produce, just read from JSON instead of generated at request time.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.schemas.ast import ContractAST
from app.schemas.billing import Invoice, UsagePeriod
from app.schemas.dsl import PricingDSL

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"

VENDOR_IDS = ["megacloud", "salesforge", "nimbuspay", "crestline", "peakservers"]


def load_vendor(vendor_id: str):
    d = FIXTURES_DIR / vendor_id
    ast = ContractAST.model_validate_json((d / "ast.json").read_text())
    dsl = PricingDSL.model_validate_json((d / "dsl.json").read_text())
    usage = [UsagePeriod.model_validate(u) for u in json.loads((d / "usage.json").read_text())]
    invoices = [Invoice.model_validate(i) for i in json.loads((d / "invoices.json").read_text())]
    meta = json.loads((d / "meta.json").read_text())
    return ast, dsl, ast.documents, usage, invoices, meta


def load_all_vendors():
    return {vid: load_vendor(vid) for vid in VENDOR_IDS}


def load_proposal():
    d = DATA_DIR / "proposal"
    ast = ContractAST.model_validate_json((d / "ast.json").read_text())
    dsl = PricingDSL.model_validate_json((d / "dsl.json").read_text())
    meta = json.loads((d / "meta.json").read_text())
    return ast, dsl, ast.documents, meta


def load_diff_pair():
    d = DATA_DIR / "diff_pair"
    ast_v1 = ContractAST.model_validate_json((d / "v1_ast.json").read_text())
    dsl_v1 = PricingDSL.model_validate_json((d / "v1_dsl.json").read_text())
    ast_v2 = ContractAST.model_validate_json((d / "v2_ast.json").read_text())
    dsl_v2 = PricingDSL.model_validate_json((d / "v2_dsl.json").read_text())
    return (ast_v1, dsl_v1), (ast_v2, dsl_v2)


def load_benchmarks():
    return json.loads((DATA_DIR / "benchmarks.json").read_text())
