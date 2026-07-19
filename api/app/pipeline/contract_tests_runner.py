"""Contract Unit Tests (F8) -- runs a vendor's contract_tests.yaml against
the compiled DSL. Legal/procurement teams write assertions in YAML; this
runs them the same way a CI pipeline runs unit tests, using the same
Billing Engine and Precedence Resolver that power reconciliation -- so a
passing contract test is a real guarantee, not a mock.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import yaml
from pydantic import BaseModel

from app.pipeline import billing_engine, precedence
from app.schemas.ast import DocumentRef
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import PricingDSL


class TestResult(BaseModel):
    name: str
    type: str
    status: str  # "PASS" | "FAIL"
    detail: str


class ContractTestReport(BaseModel):
    vendor_id: str
    results: list[TestResult]

    @property
    def pass_count(self) -> int:
        return len([r for r in self.results if r.status == "PASS"])

    @property
    def fail_count(self) -> int:
        return len([r for r in self.results if r.status == "FAIL"])

    @property
    def all_passed(self) -> bool:
        return self.fail_count == 0


def _compare(actual, op: str, value) -> bool:
    try:
        a, v = Decimal(str(actual)), Decimal(str(value))
    except (InvalidOperation, TypeError):
        a, v = str(actual), str(value)
    ops = {
        "<=": lambda x, y: x <= y, ">=": lambda x, y: x >= y, "==": lambda x, y: x == y,
        "!=": lambda x, y: x != y, "<": lambda x, y: x < y, ">": lambda x, y: x > y,
    }
    return ops[op](a, v)


def run_scenario(dsl: PricingDSL, test: dict) -> tuple[bool, str]:
    """Contract tests exercise the compiled DSL itself, independent of
    whether the underlying document has been executed yet -- a Pre-Sign
    Review test suite for an unsigned proposal must be able to assert
    "seats: 600 -> expect $3,600" against that proposal's own clauses.
    Reconciliation (real invoices) is the only place `executed` gates
    precedence; see app/pipeline/precedence.py.
    """
    ps = date.fromisoformat(test["period_start"])
    pe = date.fromisoformat(test["period_end"])
    usage_spec = test.get("usage") or {}
    usage = UsagePeriod(period_start=ps, period_end=pe, seats=usage_spec.get("seats"), units=usage_spec.get("units") or {})
    effective = precedence.effective_rules_dict(dsl, ps, documents=None)
    invoice, _ = billing_engine.compute_expected_invoice(effective, usage, ps, pe)
    expected = Decimal(str(test["expect_total"]))
    passed = invoice.total == expected
    return passed, f"computed {invoice.total}, expected {expected}"


def run_invariant(dsl: PricingDSL, test: dict) -> tuple[bool, str]:
    rule_key = test["rule_key"]
    matching = [r for r in dsl.rules if r.rule_key == rule_key]
    op = test["operator"]
    if op == "not_present":
        passed = len(matching) == 0
        return passed, f"{len(matching)} rule(s) found for '{rule_key}'"
    if not matching:
        return False, f"No rule found for rule_key '{rule_key}'"
    field = test["field"]
    value = test["value"]
    failures = []
    for r in matching:
        if field not in r.params:
            failures.append(f"{r.rule_id}: field '{field}' missing")
            continue
        if not _compare(r.params[field], op, value):
            failures.append(f"{r.rule_id}.{field} = {r.params[field]} fails '{op} {value}'")
    if failures:
        return False, "; ".join(failures)
    return True, f"All {len(matching)} rule(s) satisfy {field} {op} {value}"


def run_contract_tests(yaml_text: str, dsl: PricingDSL, docs: list[DocumentRef]) -> ContractTestReport:
    spec = yaml.safe_load(yaml_text)
    results = []
    for test in spec.get("tests", []):
        try:
            if test["type"] == "scenario":
                passed, detail = run_scenario(dsl, test)
            elif test["type"] == "invariant":
                passed, detail = run_invariant(dsl, test)
            else:
                passed, detail = False, f"Unknown test type '{test['type']}'"
        except Exception as exc:  # a malformed test is a FAIL, not a crash
            passed, detail = False, f"Error running test: {exc}"
        results.append(TestResult(name=test["name"], type=test["type"], status="PASS" if passed else "FAIL", detail=detail))
    return ContractTestReport(vendor_id=spec.get("vendor_id", "unknown"), results=results)
