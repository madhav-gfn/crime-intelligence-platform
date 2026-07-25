from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(sociology_router)


@app.get("/health")
def health():
    return {"status": "ok", "districts_loaded": len(store.df) if store.df is not None else 0}
