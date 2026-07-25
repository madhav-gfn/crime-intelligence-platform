from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics_store import store
from app.routers.financial import router as financial_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Financial Crime Analysis Service",
    description=(
        "Financial crime / transaction analysis (pillar 7): rule-based risk scoring over the "
        "real IBM AML benchmark dataset (5.08M transactions, 515k accounts, real ground-truth "
        "laundering labels). Unlike the other services, this one runs on real transaction data "
        "end to end - see /api/financial/evaluate for the rule engine's actual precision/recall "
        "against ground truth, and README.md for why those numbers are honestly modest."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(financial_router)


@app.get("/health")
def health():
    return {"status": "ok", "accounts_loaded": len(store.accounts) if store.accounts is not None else 0}
