from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_adapter import usage_rows_to_pydantic, vendor_ast_dsl
from app.models_db import Vendor
from app.pipeline.forecast import add_month, leakage_headline

router = APIRouter(prefix="/api/vendors", tags=["forecast"])


@router.get("/{vendor_id}/forecast")
def vendor_forecast(vendor_id: str, months: int = 36, db: Session = Depends(get_db)):
    """F2 -- 36-month deterministic replay forward. No ML: this is contract
    replay, holding usage at the last known baseline."""
    v = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
    if v is None:
        raise HTTPException(404, f"Vendor '{vendor_id}' not found")
    ast, dsl = vendor_ast_dsl(v)
    usage = usage_rows_to_pydantic(v.usage_periods)
    if not usage:
        raise HTTPException(400, "No usage history to forecast from")
    last_usage = usage[-1]
    forecast_start = add_month(last_usage.period_start)
    result = leakage_headline(ast, dsl, last_usage, forecast_start, months=months)
    return {"vendor_id": vendor_id, **result}
