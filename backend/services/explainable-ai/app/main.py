from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analytics_store import store
from app.routers.explainability import router as explainability_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Explainable AI Service",
    description=(
        "Explainable AI / transparent analytics (pillar 9). Six of the seven analytics services "
        "are transparent by construction (rule thresholds, backtested selection, percentile "
        "calibration) - see /api/explainability/methodology. This service adds real, validated "
        "SHAP explanations (shap.TreeExplainer, exact for tree ensembles) for the one actual "
        "black-box model in the platform: offender-profiling's Random Forest recidivism classifier."
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
app.include_router(explainability_router)


@app.get("/health")
def health():
    return {"status": "ok", "persons_explained": len(store.shap_values) if store.shap_values is not None else 0}
