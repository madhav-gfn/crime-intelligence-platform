from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Permissive for local/demo use; tighten to the actual frontend origin before
# this goes anywhere near a real deployment (see auth-governance service).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(network_router)


@app.get("/health")
def health():
    return {"status": "ok", "nodes_loaded": store.graph.number_of_nodes()}
