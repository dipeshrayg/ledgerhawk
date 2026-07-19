"""Contract test runner (F8/F9): existing vendors' contract_tests.yaml must
all PASS (the CONTRACT is fine, only invoices misbehave). The TalentBridge
proposal must show a deliberate FAIL, per acceptance criteria.
"""

from app.pipeline import loader
from app.pipeline.contract_tests_runner import run_contract_tests

FIXTURES = loader.FIXTURES_DIR
DATA_DIR = loader.DATA_DIR


def test_all_five_vendor_contract_tests_pass():
    for vendor_id in loader.VENDOR_IDS:
        ast, dsl, docs, usage, invoices, meta = loader.load_vendor(vendor_id)
        yaml_text = (FIXTURES / vendor_id / "contract_tests.yaml").read_text()
        report = run_contract_tests(yaml_text, dsl, docs)
        assert report.all_passed, f"{vendor_id} contract tests failed: {[r for r in report.results if r.status == 'FAIL']}"
        assert report.pass_count >= 1


def test_proposal_has_a_deliberate_failing_test():
    ast, dsl, docs, meta = loader.load_proposal()
    yaml_text = (DATA_DIR / "proposal" / "contract_tests.yaml").read_text()
    report = run_contract_tests(yaml_text, dsl, docs)
    assert not report.all_passed
    assert report.fail_count >= 1
    failing = [r for r in report.results if r.status == "FAIL"]
    assert any("quarterly" in r.name.lower() or "annual" in r.name.lower() for r in failing)


def test_invariant_not_present_operator():
    ast, dsl, docs, usage, invoices, meta = loader.load_vendor("nimbuspay")
    yaml_text = (FIXTURES / "nimbuspay" / "contract_tests.yaml").read_text()
    report = run_contract_tests(yaml_text, dsl, docs)
    not_present_test = next(r for r in report.results if "No escalation" in r.name)
    assert not_present_test.status == "PASS"
