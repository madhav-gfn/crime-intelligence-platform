from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics_store import store
from app.routers.forecasting import router as forecasting_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Crime Intelligence Platform - Crime Forecasting Service",
    description=(
        "Crime forecasting (pillar 8): backtested district-level forecasts (TOTAL / VIOLENT / "
        "PROPERTY crime) built from real NCRB 2001-2012 annual district-wise data - not "
        "synthetic FIRs. Every forecast is backed by a genuine train(2001-09)/test(2010-12) "
        "backtest against a naive baseline - see /api/forecasting/stats for how often the "
        "trend/moving-average models actually beat 'predict no change from last year'."
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

app.include_router(forecasting_router)


@app.get("/health")
def health():
    return {"status": "ok", "series_loaded": len(store.df) if store.df is not None else 0}
