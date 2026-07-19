from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db_adapter import invoice_rows_to_pydantic, usage_rows_to_pydantic, vendor_ast_dsl
from app.models_db import Vendor
from app.pipeline import copilot as copilot_pipeline
from app.pipeline import reconciliation
from app.pipeline.violation_graph import ViolationGraph

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class Question(BaseModel):
    question: str


def _build_graph(db: Session):
    findings, vendor_names, invoice_counts = [], {}, {}
    for v in db.query(Vendor).all():
        vendor_names[v.vendor_id] = v.vendor_name
        ast, dsl = vendor_ast_dsl(v)
        usage = usage_rows_to_pydantic(v.usage_periods)
        invoices = invoice_rows_to_pydantic(v.invoices, v.vendor_id)
        invoice_counts[v.vendor_id] = len(invoices)
        results = reconciliation.reconcile_all(dsl, ast.documents, usage, invoices)
        findings.extend(r.findings[0] for r in results if r.findings)
    return ViolationGraph(findings, vendor_names), vendor_names, invoice_counts


@router.post("/ask")
def ask(payload: Question, db: Session = Depends(get_db)):
    """F10 -- Audit Copilot. Answers are always sourced from the Violation
    Graph, never free-generated -- see app/pipeline/copilot.py."""
    graph, vendor_names, invoice_counts = _build_graph(db)
    return copilot_pipeline.answer(payload.question, graph, vendor_names, invoice_counts)


@router.get("/suggested-questions")
def suggested_questions():
    return {"questions": [
        "Which vendors violated their contracts?",
        "Show overcharges above $5,000",
        "Which clauses caused the most loss?",
        "Why did MegaCloud's cost jump?",
        "What is our total recovered leakage?",
        "Which vendor has the highest risk?",
        "Show findings for SalesForge",
        "What's our compliance rate?",
    ]}
