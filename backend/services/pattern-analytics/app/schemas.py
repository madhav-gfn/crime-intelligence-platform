from typing import Optional

from pydantic import BaseModel


class DatasetStats(BaseModel):
    total_firs: int
    date_range_start: str
    date_range_end: str
    distinct_districts: int
    distinct_crime_types: int
    crime_type_counts: dict[str, int]


class HotspotCluster(BaseModel):
    cluster_id: int
    point_count: int
    centroid_lat: float
    centroid_lon: float
    radius_km: float
    top_district: str
    crime_type_breakdown: dict[str, int]
    sample_fir_ids: list[str]
    geo_precise_fraction: float  # fraction of members with a real (not jittered-fallback) geocode - see data/schemas doc


class HotspotResponse(BaseModel):
    filters: dict
    eps_km: float
    min_points: int
    total_points_considered: int
    noise_points: int
    clusters: list[HotspotCluster]


class DistrictSeverity(BaseModel):
    district: str
    state: str
    total_crimes: int
    violent_crime_ratio: float
    property_crime_ratio: float
    avg_property_value_inr: float
    crime_type_diversity: float
    unresolved_ratio: float
    severity_tier: str
    pca_x: float
    pca_y: float


class DistrictSeverityResponse(BaseModel):
    min_crimes_threshold: int
    districts_included: int
    tiers: list[DistrictSeverity]


class TrendPoint(BaseModel):
    bucket: str
    count: int


class TrendResponse(BaseModel):
    granularity: str
    filters: dict
    points: list[TrendPoint]


class EmergingHotspot(BaseModel):
    district: str
    state: str
    crime_type_code: str
    recent_count: int
    baseline_count: int
    recent_period_days: int
    baseline_period_days: int
    pct_change: Optional[float]
    flagged_reason: str


class EmergingResponse(BaseModel):
    recent_window_days: int
    baseline_window_days: int
    min_recent_count: int
    alerts: list[EmergingHotspot]


class SimilarCase(BaseModel):
    fir_id: str
    similarity: float
    crime_type_code: str
    district: str
    state: str
    date_occurred: str
    status: str
    matching_features: list[str]


class SimilarCasesResponse(BaseModel):
    source_fir_id: str
    source_crime_type: str
    top_n: int
    results: list[SimilarCase]
