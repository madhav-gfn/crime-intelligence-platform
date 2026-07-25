from fastapi import APIRouter, HTTPException, Query

from app.analytics_store import store
from app.schemas import (
    AccountProfile, DatasetStats, EvaluationResponse, PathResponse, PatternsResponse,
    SuspiciousAccountsResponse,
)

router = APIRouter(prefix="/api/financial", tags=["financial-crime-analysis"])


@router.get("/stats", response_model=DatasetStats)
def get_stats():
    return store.stats()


@router.get("/account/{account_id}", response_model=AccountProfile)
def get_account(account_id: str):
    result = store.account_profile(account_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"account_id '{account_id}' not found")
    return result


@router.get("/suspicious-accounts", response_model=SuspiciousAccountsResponse)
def get_suspicious_accounts(
    risk_tier: str = Query("HIGH", pattern="^(LOW|MEDIUM|HIGH)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    return store.suspicious_accounts(risk_tier=risk_tier, limit=limit)


@router.get("/patterns", response_model=PatternsResponse)
def get_patterns(
    typology: str | None = Query(None, description="e.g. FAN-OUT, CYCLE, FAN-IN, GATHER-SCATTER"),
    limit: int = Query(50, ge=1, le=370),
):
    return store.get_patterns(typology=typology, limit=limit)


@router.get("/path", response_model=PathResponse)
def get_path(source: str, target: str):
    return store.path(source, target)


@router.get("/evaluate", response_model=EvaluationResponse)
def get_evaluation():
    return store.evaluation()
