"""Seeds the SQLite DB from the checked-in demo fixtures. Idempotent --
skips vendors that already exist so re-running `run.sh` doesn't duplicate
data. This is the "zero-key demo mode" boundary: everything the API serves
after this point comes from real DB rows, indistinguishable from what a
live extraction pipeline would have produced.
"""
import json

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models_db import DiffPairRow, InvoiceRow, ProposalRow, UsagePeriodRow, Vendor
from app.pipeline import loader


def seed_if_empty(db: Session):
    Base.metadata.create_all(bind=engine)

    if db.query(Vendor).count() == 0:
        for vendor_id in loader.VENDOR_IDS:
            ast, dsl, docs, usage, invoices, meta = loader.load_vendor(vendor_id)
            contract_tests = (loader.FIXTURES_DIR / vendor_id / "contract_tests.yaml").read_text()
            vendor = Vendor(
                vendor_id=vendor_id, vendor_name=meta["vendor_name"], category=meta["category"],
                ast_json=json.loads(ast.model_dump_json()), dsl_json=json.loads(dsl.model_dump_json()),
                contract_tests_yaml=contract_tests,
            )
            db.add(vendor)
            db.flush()
            for u in usage:
                db.add(UsagePeriodRow(
                    vendor_pk=vendor.id, period_start=u.period_start, period_end=u.period_end,
                    seats=u.seats, units_json=u.units, seat_change_json=u.seat_change,
                ))
            for inv in invoices:
                db.add(InvoiceRow(
                    vendor_pk=vendor.id, invoice_id=inv.invoice_id, period_start=inv.period_start,
                    period_end=inv.period_end, invoice_date=inv.invoice_date,
                    line_items_json=[li.model_dump(mode="json") for li in inv.line_items],
                    total_amount=inv.total_amount, source="seed",
                ))
        db.commit()

    if db.query(ProposalRow).count() == 0:
        ast, dsl, docs, meta = loader.load_proposal()
        contract_tests = (loader.DATA_DIR / "proposal" / "contract_tests.yaml").read_text()
        db.add(ProposalRow(
            proposal_id="talentbridge_proposal", vendor_name=meta["vendor_name"], category=meta["category"],
            ast_json=json.loads(ast.model_dump_json()), dsl_json=json.loads(dsl.model_dump_json()),
            contract_tests_yaml=contract_tests,
        ))
        db.commit()

    if db.query(DiffPairRow).count() == 0:
        (ast_v1, dsl_v1), (ast_v2, dsl_v2) = loader.load_diff_pair()
        db.add(DiffPairRow(
            pair_id="datavault", vendor_name="DataVault Storage",
            v1_ast_json=json.loads(ast_v1.model_dump_json()), v1_dsl_json=json.loads(dsl_v1.model_dump_json()),
            v2_ast_json=json.loads(ast_v2.model_dump_json()), v2_dsl_json=json.loads(dsl_v2.model_dump_json()),
        ))
        db.commit()


def main():
    db = SessionLocal()
    try:
        seed_if_empty(db)
        print(f"Vendors: {db.query(Vendor).count()}, Invoices: {db.query(InvoiceRow).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
