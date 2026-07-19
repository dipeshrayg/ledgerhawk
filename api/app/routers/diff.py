from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models_db import DiffPairRow
from app.pipeline.diff_engine import diff_contracts
from app.schemas.ast import ContractAST
from app.schemas.billing import UsagePeriod
from app.schemas.dsl import PricingDSL

router = APIRouter(prefix="/api/diff", tags=["diff"])


@router.get("/{pair_id}")
def get_diff(pair_id: str, db: Session = Depends(get_db)):
    """F6 -- Contract Version Diff. Categorized rule-level changes with a
    36-month dollar-impact estimate, rendered like a GitHub diff on the
    frontend."""
    row = db.query(DiffPairRow).filter(DiffPairRow.pair_id == pair_id).first()
    if row is None:
        return {"error": f"No diff pair '{pair_id}'"}, 404
    ast_v1 = ContractAST.model_validate(row.v1_ast_json)
    dsl_v1 = PricingDSL.model_validate(row.v1_dsl_json)
    ast_v2 = ContractAST.model_validate(row.v2_ast_json)
    dsl_v2 = PricingDSL.model_validate(row.v2_dsl_json)

    baseline = UsagePeriod(period_start=date(2026, 8, 1), period_end=date(2026, 8, 1), units={"tb": 500})
    result = diff_contracts(ast_v1, dsl_v1, ast_v2, dsl_v2, baseline, date(2026, 8, 1), months=36)
    return {
        "pair_id": pair_id, "vendor_name": row.vendor_name,
        "v1": ast_v1.model_dump(mode="json"), "v2": ast_v2.model_dump(mode="json"),
        **result,
    }
