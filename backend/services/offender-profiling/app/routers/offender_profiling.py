from fastapi import APIRouter, HTTPException, Query

from app.analytics_store import store
from app.schemas import ModelInfo, PersonRiskProfile, PredictResponse, RiskListResponse

router = APIRouter(prefix="/api/offender-profiling", tags=["offender-profiling"])


@router.get("/model-info", response_model=ModelInfo)
def get_model_info():
    return store.model_info()


@router.get("/person/{person_id}", response_model=PersonRiskProfile)
def get_person(person_id: str):
    result = store.person_profile(person_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"person_id '{person_id}' not found")
    return result


@router.get("/risk-list", response_model=RiskListResponse)
def get_risk_list(
    risk_tier: str = Query("HIGH", pattern="^(LOW|MEDIUM|HIGH)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    return store.risk_list(risk_tier=risk_tier, limit=limit)


@router.get("/predict", response_model=PredictResponse)
def predict(
    prior_case_count: int = Query(..., ge=0),
    distinct_prior_crime_types: int = Query(..., ge=0),
    prior_violent_count: int = Query(0, ge=0),
    prior_property_count: int = Query(0, ge=0),
    days_since_first_case: int = Query(0, ge=0),
    current_is_violent: bool = Query(False),
    current_is_property: bool = Query(False),
    gender: str = Query("M", pattern="^(M|F)$"),
    age: int = Query(..., ge=0, le=120),
    state: str = Query("OTHER"),
):
    return store.predict(
        prior_case_count, distinct_prior_crime_types, prior_violent_count, prior_property_count,
        days_since_first_case, current_is_violent, current_is_property, gender, age, state,
    )
