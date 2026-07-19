"""API-level smoke tests using FastAPI's TestClient -- each feature's HTTP
surface returns real, computed data (not stubs)."""
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.seed import seed_if_empty


@pytest.fixture(scope="module")
def client():
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_vendors_list_has_5_vendors(client):
    r = client.get("/api/vendors")
    assert r.status_code == 200
    assert len(r.json()["vendors"]) == 5


def test_dashboard_total_recovered_matches_e2e(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    assert r.json()["total_recovered"] == "86420.40"
    assert r.json()["compliance_pct"] == pytest.approx(76.7, abs=0.1)


def test_rule_inspector_shows_email_precedence(client):
    r = client.get("/api/vendors/megacloud/rule-inspector")
    assert r.status_code == 200
    discount = next(t for t in r.json()["effective_terms"] if t["rule_key"] == "pricing.discount.default")
    assert discount["doc_id"] == "email1"


def test_vendor_404(client):
    r = client.get("/api/vendors/doesnotexist/rule-inspector")
    assert r.status_code == 404


def test_forecast_endpoint(client):
    r = client.get("/api/vendors/megacloud/forecast?months=36")
    assert r.status_code == 200
    assert r.json()["headline"] is not None


def test_calendar_all_events_forward_looking(client):
    r = client.get("/api/calendar")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) > 0
    assert all(e["days_remaining"] >= 0 for e in events)


def test_dispute_letter_cites_real_finding(client):
    findings = client.get("/api/vendors/megacloud/findings").json()["findings"]
    invoice_id = findings[0]["invoice_id"]
    r = client.get(f"/api/vendors/megacloud/invoices/{invoice_id}/dispute-letter")
    assert r.status_code == 200
    body = r.json()
    assert body["finding"]["clause_quote"] in body["letter"]


def test_diff_endpoint(client):
    r = client.get("/api/diff/datavault")
    assert r.status_code == 200
    assert float(r.json()["dollar_impact_36mo"]) > 0


def test_presign_endpoint_shows_failing_contract_test(client):
    r = client.get("/api/presign/talentbridge_proposal")
    assert r.status_code == 200
    assert r.json()["contract_tests"]["fail_count"] >= 1


def test_negotiate_endpoint(client):
    r = client.post("/api/presign/talentbridge_proposal/negotiate")
    assert r.status_code == 200
    assert float(r.json()["expected_savings_36mo"]) > 0


def test_copilot_endpoint(client):
    r = client.post("/api/copilot/ask", json={"question": "What is our total recovered leakage?"})
    assert r.status_code == 200
    assert "86,420.40" in r.json()["answer"]


def test_connectors_list(client):
    r = client.get("/api/connectors")
    assert r.status_code == 200
    assert len(r.json()["connectors"]) == 3


def test_mock_erp_poll_ingests_and_logs_ci_run(client):
    r = client.post("/api/connectors/mock-erp/poll")
    assert r.status_code == 200
    assert r.json()["polled"] == 5  # one per vendor
