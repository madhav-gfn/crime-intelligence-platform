from contextlib import asynccontextmanager

from fastapi import FastAPI

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

# No app-level CORSMiddleware - Zoho Catalyst AppSail's edge intercepts the
# CORS preflight (OPTIONS) before it ever reaches this app, and injects its
# own Access-Control-Allow-Origin header on real responses too, based on the
# per-service "Authorized Domains" allowlist configured in the Catalyst
# Console (Cloud Scale -> Authentication). Adding our own CORSMiddleware on
# top produced two Access-Control-Allow-Origin headers on the same response
# (ours and Catalyst's), which browsers reject outright - see
# docs/PROJECT_STATUS.md for the debugging trail. CORS is Catalyst's
# responsibility now, not this app's.
app.include_router(offender_profiling_router)


@app.get("/health")
def health():
    return {"status": "ok", "persons_scored": len(store.scores) if store.scores is not None else 0}
