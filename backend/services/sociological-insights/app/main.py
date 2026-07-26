from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analytics_store import store
from app.routers.sociology import router as sociology_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Sociological Insights Service",
    description=(
        "Sociological crime insights (pillar 4): joins real Census 2011 district socioeconomic "
        "data against NCRB-calibrated crime rates to surface correlations, rankings, and scatter "
        "data. Deliberately excludes caste/religion composition from any correlation - see README "
        "for the attribute-decoupling rationale."
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
app.include_router(sociology_router)


@app.get("/health")
def health():
    return {"status": "ok", "districts_loaded": len(store.df) if store.df is not None else 0}
