from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.graph_store import store
from app.routers.network import router as network_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Network Analysis Service",
    description=(
        "Criminal network & relationship analysis: co-accused graphs, organized-group "
        "detection, key-actor ranking, association paths, and repeat-offender lookups. "
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
app.include_router(network_router)


@app.get("/health")
def health():
    return {"status": "ok", "nodes_loaded": store.graph.number_of_nodes()}
