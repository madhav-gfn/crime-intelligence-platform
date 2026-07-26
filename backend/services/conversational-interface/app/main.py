from contextlib import asynccontextmanager

import httpx
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.nlu import DistrictIndex
from app.orchestrator import Orchestrator
from app.routers.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    fir = pd.read_csv(settings.data_seed_dir / "fir.csv", usecols=["district"])
    app.state.district_index = DistrictIndex(fir["district"].dropna().unique().tolist())
    app.state.http_client = httpx.AsyncClient()
    app.state.orchestrator = Orchestrator(app.state.http_client, settings)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Crime Intelligence Platform - Conversational Interface",
    description=(
        "Conversational interface (pillar 1). Deterministic, rule-based natural-language query "
        "router over the platform's other analytics services - no LLM API key is available in this "
        "environment, so this implements the reachable part of the research doc's dialogue-engine "
        "vision (multi-turn context tracking, intent routing) without the unreachable parts "
        "(LLM-based NLU, Whisper ASR, Kannada TTS/G2P, LangGraph). See /api/chat/capabilities."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}
