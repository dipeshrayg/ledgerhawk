from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import SessionLocal
from app.routers import calendar, connectors, copilot, dashboard, diff, forecast, presign, vendors
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="LedgerHawk API", description="CI/CD for Enterprise Contracts", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": settings.is_demo_mode, "llm_mode": settings.llm_mode}


app.include_router(vendors.router)
app.include_router(dashboard.router)
app.include_router(forecast.router)
app.include_router(calendar.router)
app.include_router(diff.router)
app.include_router(presign.router)
app.include_router(copilot.router)
app.include_router(connectors.router)
