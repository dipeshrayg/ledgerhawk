from decimal import Decimal

from app.connectors.csv_watcher import CSVDropFolderConnector
from app.connectors.mock_erp import MockERPConnector
from app.connectors.stripe_sandbox import StripeSandboxConnector


def test_mock_erp_streams_one_invoice_per_vendor_per_poll():
    connector = MockERPConnector(vendor_ids=["peakservers"])
    total_remaining = connector.remaining()
    assert total_remaining == 12
    batch1 = connector.poll()
    assert len(batch1) == 1
    assert connector.remaining() == 11
    batch2 = connector.poll()
    assert batch2[0].invoice_id != batch1[0].invoice_id


def test_mock_erp_exhausts_after_12_polls():
    connector = MockERPConnector(vendor_ids=["crestline"])
    seen = []
    for _ in range(12):
        seen.extend(connector.poll())
    assert len(seen) == 12
    assert connector.poll() == []


def test_csv_drop_folder_parses_new_invoice(tmp_path):
    folder = tmp_path / "dropfolder"
    connector = CSVDropFolderConnector(folder)
    csv_path = folder / "acme_202609.csv"
    csv_path.write_text(
        "vendor_id,invoice_id,period_start,period_end,invoice_date,line_item_description,line_item_amount\n"
        "acme,acme-202609,2026-09-01,2026-09-30,2026-10-03,Flat fee,250.00\n"
        "acme,acme-202609,2026-09-01,2026-09-30,2026-10-03,Per-unit usage,480.00\n"
    )
    invoices = connector.poll()
    assert len(invoices) == 1
    assert invoices[0].total_amount == Decimal("730.00")
    assert connector.poll() == []  # already seen, no duplicates


def test_stripe_connector_disabled_without_key():
    connector = StripeSandboxConnector()
    assert connector.enabled is False
    assert connector.poll() == []
