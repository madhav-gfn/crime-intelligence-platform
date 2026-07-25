from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics_store import store
from app.rbac import require_role
from app.schemas import MethodologyOverview, ModelExplainabilityInfo, PersonExplanation, PredictExplainResponse

router = APIRouter(prefix="/api/explainability", tags=["explainability"])


@router.get("/methodology", response_model=MethodologyOverview)
def get_methodology(claims: dict = Depends(require_role("ANALYST"))):
    return store.methodology()


@router.get("/model-info", response_model=ModelExplainabilityInfo)
def get_model_info(claims: dict = Depends(require_role("ANALYST"))):
    return store.model_info()


@router.get("/person/{person_id}", response_model=PersonExplanation)
def get_person_explanation(person_id: str, claims: dict = Depends(require_role("INVESTIGATOR"))):
    result = store.person_explanation(person_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"person_id '{person_id}' not found")
    return result


@router.get("/predict-explain", response_model=PredictExplainResponse)
def predict_explain(
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
    claims: dict = Depends(require_role("ANALYST")),
):
    return store.predict_explain(
        prior_case_count, distinct_prior_crime_types, prior_violent_count, prior_property_count,
        days_since_first_case, current_is_violent, current_is_property, gender, age, state,
    )
