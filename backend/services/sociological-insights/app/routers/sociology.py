from fastapi import APIRouter, HTTPException, Query

from app.analytics_store import ALLOWED_INDICATORS, CRIME_METRICS, store
from app.schemas import (
    CorrelationsResponse, DistrictListResponse, DistrictProfile, RankingResponse, ScatterResponse,
)

router = APIRouter(prefix="/api/sociology", tags=["sociological-insights"])

_SORTABLE_FIELDS = set(ALLOWED_INDICATORS) | set(CRIME_METRICS)


@router.get("/districts", response_model=DistrictListResponse)
def get_districts():
    return store.districts()


@router.get("/district/{district}", response_model=DistrictProfile)
def get_district_profile(district: str):
    result = store.district_profile(district)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district '{district}' not found in the joined dataset")
    return result


@router.get("/correlations", response_model=CorrelationsResponse)
def get_correlations(
    min_population: int = Query(0, ge=0, description="Exclude districts below this population from the correlation"),
):
    return store.correlations(min_population=min_population)


@router.get("/rankings", response_model=RankingResponse)
def get_rankings(
    sort_by: str = Query(..., description=f"One of: {', '.join(sorted(_SORTABLE_FIELDS))}"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=200),
    min_population: int = Query(0, ge=0),
):
    if sort_by not in _SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"sort_by must be one of: {sorted(_SORTABLE_FIELDS)}")
    return store.rankings(sort_by=sort_by, order=order, limit=limit, min_population=min_population)


@router.get("/scatter/{indicator}", response_model=ScatterResponse)
def get_scatter(
    indicator: str,
    crime_metric: str = Query("crime_rate_per_100k"),
):
    if indicator not in ALLOWED_INDICATORS:
        raise HTTPException(status_code=400, detail=f"indicator must be one of: {ALLOWED_INDICATORS}")
    if crime_metric not in CRIME_METRICS:
        raise HTTPException(status_code=400, detail=f"crime_metric must be one of: {CRIME_METRICS}")
    return store.scatter(indicator, crime_metric)
