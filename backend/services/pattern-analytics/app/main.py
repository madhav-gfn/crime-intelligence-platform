from contextlib import asynccontextmanager

from fastapi import FastAPI

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

# No app-level CORSMiddleware - Zoho Catalyst AppSail's edge intercepts the
# CORS preflight (OPTIONS) before it ever reaches this app, and injects its
# own Access-Control-Allow-Origin header on real responses too, based on the
# per-service "Authorized Domains" allowlist configured in the Catalyst
# Console (Cloud Scale -> Authentication). Adding our own CORSMiddleware on
# top produced two Access-Control-Allow-Origin headers on the same response
# (ours and Catalyst's), which browsers reject outright - see
# docs/PROJECT_STATUS.md for the debugging trail. CORS is Catalyst's
# responsibility now, not this app's.
app.include_router(patterns_router)


@app.get("/health")
def health():
    return {"status": "ok", "firs_loaded": len(store.df) if store.df is not None else 0}
