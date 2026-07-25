from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics_store import store
from app.routers.patterns import router as patterns_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Pattern Analytics Service",
    description=(
        "Crime pattern & trend analytics: DBSCAN geospatial hotspot clustering, "
        "PCA+KMeans district severity tiering, temporal trend analysis (monthly/"
        "weekday/hourly), emerging-spike detection, and MO-similarity case matching. "
        "Runs on the calibrated synthetic seed dataset (data/seed/) - see "
        "data/schemas/synthetic_fir_schema.md for provenance."
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

app.include_router(patterns_router)


@app.get("/health")
def health():
    return {"status": "ok", "firs_loaded": len(store.df) if store.df is not None else 0}
