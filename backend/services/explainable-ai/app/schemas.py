from pydantic import BaseModel


class FeatureContribution(BaseModel):
    feature: str
    feature_value: float
    shap_value: float


class MethodologyEntry(BaseModel):
    service: str
    approach: str
    transparency_mechanism: str


class MethodologyOverview(BaseModel):
    summary: str
    pillars: list[MethodologyEntry]


class ConcordanceInfo(BaseModel):
    metric: str
    value: float
    note: str


class ModelExplainabilityInfo(BaseModel):
    method: str
    base_value: float
    mean_abs_shap_by_feature: dict[str, float]
    top_5_drivers: list[str]
    concordance_with_rf_builtin_importance: ConcordanceInfo
    total_persons_explained: int
    max_reconstruction_error: float


class PersonExplanation(BaseModel):
    person_id: str
    full_name: str | None
    risk_tier: str
    predicted_reoffend_probability_365d: float
    base_value: float
    reconstruction_error: float
    top_drivers: list[FeatureContribution]
    all_contributions: list[FeatureContribution]


class PredictExplainResponse(BaseModel):
    predicted_reoffend_probability_365d: float
    risk_tier: str
    base_value: float
    top_drivers: list[FeatureContribution]
    all_contributions: list[FeatureContribution]
    inputs: dict
