from pydantic import BaseModel


class PersonRiskProfile(BaseModel):
    person_id: str
    full_name: str | None
    gender: str | None
    age: int | None
    address_district: str | None
    address_state: str | None
    prior_case_count: int
    distinct_crime_types_count: int
    predicted_reoffend_probability_365d: float
    risk_tier: str


class RiskListResponse(BaseModel):
    risk_tier: str
    count: int
    persons: list[PersonRiskProfile]


class ModelComparisonEntry(BaseModel):
    precision: float
    recall: float
    f1: float
    roc_auc: float | None


class ModelInfo(BaseModel):
    follow_up_days: int
    dataset_max_date: str
    eligibility_cutoff_date: str
    total_case_appearances: int
    eligible_case_appearances: int
    censored_case_appearances: int
    positive_rate: float
    train_appearances: int
    test_appearances: int
    train_persons: int
    test_persons: int
    selected_model: str
    model_comparison: dict[str, ModelComparisonEntry]
    feature_importances: dict[str, float]
    risk_tier_thresholds: dict[str, float]
    risk_tier_counts: dict[str, int]
    total_accused_persons_scored: int


class PredictResponse(BaseModel):
    predicted_reoffend_probability_365d: float
    risk_tier: str
    model_used: str
    inputs: dict
