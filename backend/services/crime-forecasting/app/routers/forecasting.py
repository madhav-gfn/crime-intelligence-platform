from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics_store import VALID_SERIES, store
from app.rbac import require_role
from app.schemas import DatasetStats, DistrictForecastBundle, RankingResponse

router = APIRouter(prefix="/api/forecasting", tags=["crime-forecasting"])


@router.get("/stats", response_model=DatasetStats)
def get_stats(claims: dict = Depends(require_role("ANALYST"))):
    return store.stats()


@router.get("/district/{district}", response_model=DistrictForecastBundle)
def get_district_forecast(district: str, claims: dict = Depends(require_role("ANALYST"))):
    result = store.district_forecast(district)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district '{district}' not found in the forecast dataset")
    return result


@router.get("/rankings", response_model=RankingResponse)
def get_rankings(
    series: str = Query("TOTAL", pattern="^(TOTAL|VIOLENT|PROPERTY)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=200),
    claims: dict = Depends(require_role("ANALYST")),
):
    if series not in VALID_SERIES:
        raise HTTPException(status_code=400, detail=f"series must be one of: {sorted(VALID_SERIES)}")
    return store.rankings(series=series, order=order, limit=limit)
