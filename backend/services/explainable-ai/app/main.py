from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(explainability_router)


@app.get("/health")
def health():
    return {"status": "ok", "persons_explained": len(store.shap_values) if store.shap_values is not None else 0}
