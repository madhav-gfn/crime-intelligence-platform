from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analytics_store import store
from app.routers.decision_support import router as decision_support_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Investigator Decision Support Service",
    description=(
        "Investigator decision support (pillar 6): a synthesis layer over the other five "
        "analytics services rather than a sixth siloed one. Case-priority triage (transparent "
        "point-based scoring), cross-pillar person dossiers (offender risk + network + case "
        "history), and district briefings (case volume + real socioeconomic context + real "
        "forecast trend). Reads the same precomputed artifacts those services produce directly - "
        "see analytics_store.py's docstring for why, not live HTTP fan-out."
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
app.include_router(decision_support_router)


@app.get("/health")
def health():
    return {"status": "ok", "unresolved_cases_loaded": len(store.case_priority) if store.case_priority is not None else 0}
