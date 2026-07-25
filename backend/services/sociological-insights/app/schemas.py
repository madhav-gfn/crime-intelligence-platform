from pydantic import BaseModel


class DistrictSummary(BaseModel):
    state: str
    district: str
    match_type: str
    population: int
    crime_rate_per_100k: float | None


class DistrictListResponse(BaseModel):
    total_census_districts: int
    matched_districts: int
    match_rate: float
    districts: list[DistrictSummary]


class DistrictProfile(BaseModel):
    state: str
    district: str
    fir_district_label: str
    match_type: str
    match_score: float
    population: int

    # Structural socioeconomic indicators - the only fields this service
    # ever correlates against crime rates. See analytics_store.py.
    literacy_rate: float
    urbanization_rate: float
    workforce_participation_rate: float
    higher_education_rate: float
    amenity_index: float

    # Neutral demographic context, carried through from the census for
    # transparency only - deliberately never used in /correlations,
    # /rankings, or /scatter. See module docstring in
    # scripts/data_generation/sociology/build_district_join.py and the
    # "Attribute decoupling" note in this service's README.
    sc_st_share: float
    hindu_share: float
    muslim_share: float
    christian_share: float
    sikh_share: float

    total_crimes: int
    violent_crimes: int
    property_crimes: int
    violent_ratio: float
    property_ratio: float
    crime_rate_per_100k: float
    violent_crime_rate_per_100k: float
    property_crime_rate_per_100k: float


class CorrelationResult(BaseModel):
    indicator: str
    crime_metric: str
    pearson_r: float
    p_value: float
    n: int
    interpretation: str


class CorrelationsResponse(BaseModel):
    districts_included: int
    indicators_used: list[str]
    crime_metrics_used: list[str]
    excluded_fields_note: str
    results: list[CorrelationResult]


class RankingEntry(BaseModel):
    state: str
    district: str
    value: float
    population: int
    crime_rate_per_100k: float


class RankingResponse(BaseModel):
    sort_by: str
    order: str
    limit: int
    districts: list[RankingEntry]


class ScatterPoint(BaseModel):
    state: str
    district: str
    x: float
    y: float
    population: int


class ScatterResponse(BaseModel):
    indicator: str
    crime_metric: str
    points: list[ScatterPoint]
