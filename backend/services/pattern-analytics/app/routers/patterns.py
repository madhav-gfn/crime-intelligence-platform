from fastapi import APIRouter, HTTPException, Query

from app.analytics_store import store
from app.schemas import (
    DatasetStats, DistrictSeverityResponse, EmergingResponse, HotspotResponse,
    SimilarCasesResponse, TrendResponse,
)

router = APIRouter(prefix="/api/patterns", tags=["pattern-analytics"])


@router.get("/stats", response_model=DatasetStats)
def get_stats():
    return store.stats()


@router.get("/hotspots", response_model=HotspotResponse)
def get_hotspots(
    crime_type: str | None = Query(None),
    district: str | None = Query(None, description="Substring match"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    eps_km: float = Query(15.0, gt=0, description="DBSCAN neighborhood radius in km"),
    min_points: int = Query(5, ge=2, description="DBSCAN min_samples - minimum incidents to form a cluster core"),
):
    return store.hotspots(crime_type, district, start_date, end_date, eps_km, min_points)


@router.get("/district-severity", response_model=DistrictSeverityResponse)
def get_district_severity(
    min_crimes: int = Query(10, ge=1, description="Exclude districts with fewer than this many recorded crimes"),
):
    return store.district_severity(min_crimes=min_crimes)


@router.get("/trends/{granularity}", response_model=TrendResponse)
def get_trends(
    granularity: str,
    crime_type: str | None = Query(None),
    district: str | None = Query(None),
):
    if granularity not in {"monthly", "weekday", "hourly"}:
        raise HTTPException(status_code=400, detail="granularity must be one of: monthly, weekday, hourly")
    return store.trends(granularity, crime_type, district)


@router.get("/emerging", response_model=EmergingResponse)
def get_emerging(
    recent_days: int = Query(90, ge=7),
    baseline_days: int = Query(180, ge=7),
    min_recent_count: int = Query(
        3, ge=1,
        description="Lower default than you might expect: this seed dataset is ~5k FIRs spread across "
                     "~660 districts x 21 crime types over 5 years, so per-cell counts are naturally sparse. "
                     "Raise this once running against denser, real case volume.",
    ),
):
    return store.emerging(recent_days, baseline_days, min_recent_count)


@router.get("/similar-cases/{fir_id}", response_model=SimilarCasesResponse)
def get_similar_cases(fir_id: str, top_n: int = Query(10, ge=1, le=50)):
    result = store.similar_cases(fir_id, top_n)
    if result is None:
        raise HTTPException(status_code=404, detail=f"fir_id '{fir_id}' not found")
    return result
