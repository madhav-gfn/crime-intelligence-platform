from pydantic import BaseModel


class CasePriority(BaseModel):
    fir_id: str
    state: str
    district: str
    crime_type_code: str
    status: str
    date_reported: str
    age_days: int
    violent_points: int
    accused_risk_points: int
    hotspot_points: int
    stale_points: int
    priority_score: int
    priority_tier: str
    highest_accused_risk_tier: str | None


class CasePriorityListResponse(BaseModel):
    priority_tier: str | None
    count: int
    cases: list[CasePriority]


class OffenderRiskSummary(BaseModel):
    prior_case_count: int
    distinct_crime_types_count: int
    predicted_reoffend_probability_365d: float
    risk_tier: str


class Associate(BaseModel):
    person_id: str
    full_name: str | None
    shared_fir_count: int


class CaseAppearance(BaseModel):
    fir_id: str
    role: str
    crime_type_code: str
    date_reported: str
    status: str
    district: str


class PersonDossier(BaseModel):
    person_id: str
    full_name: str | None
    gender: str | None
    age: int | None
    address_district: str | None
    address_state: str | None
    offender_risk: OffenderRiskSummary | None
    network_degree: int
    top_associates: list[Associate]
    cases: list[CaseAppearance]


class SocioeconomicContext(BaseModel):
    available: bool
    literacy_rate: float | None = None
    urbanization_rate: float | None = None
    crime_rate_per_100k: float | None = None


class ForecastContext(BaseModel):
    available: bool
    last_observed_year: int | None = None
    last_observed_value: float | None = None
    forecast_2015: float | None = None
    pct_change: float | None = None
    selected_model: str | None = None


class DistrictBriefing(BaseModel):
    state: str
    district: str
    total_cases: int
    unresolved_cases: int
    violent_ratio: float
    property_ratio: float
    case_volume_percentile_rank: float
    is_hotspot: bool
    socioeconomic: SocioeconomicContext
    forecast: ForecastContext


class DecisionSupportStats(BaseModel):
    total_cases: int
    total_unresolved_cases: int
    priority_tier_counts: dict[str, int]
    priority_tier_thresholds: dict[str, int]
    stale_case_days_threshold: int
    stale_unresolved_case_count: int
    dataset_reference_date: str
