from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics_store import store
from app.routers.offender_profiling import router as offender_profiling_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Offender Profiling Service",
    description=(
        "Criminology-based offender profiling (pillar 5): a trained recidivism-risk classifier "
        "(random forest, selected over logistic regression by backtested ROC-AUC) predicting "
        "whether an accused person reoffends within 365 days of a case, replacing the earlier "
        "rule-based risk_tier placeholder. Evaluated against a real held-out test set AND the "
        "old rule baseline - see /api/offender-profiling/model-info for both."
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

app.include_router(offender_profiling_router)


@app.get("/health")
def health():
    return {"status": "ok", "persons_scored": len(store.scores) if store.scores is not None else 0}
