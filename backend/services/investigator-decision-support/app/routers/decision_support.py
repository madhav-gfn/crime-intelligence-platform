from fastapi import APIRouter, HTTPException, Query

from app.analytics_store import store
from app.schemas import (
    CasePriority, CasePriorityListResponse, DecisionSupportStats, DistrictBriefing, PersonDossier,
)

router = APIRouter(prefix="/api/decision-support", tags=["investigator-decision-support"])


@router.get("/stats", response_model=DecisionSupportStats)
def get_stats():
    return store.stats()


@router.get("/case-priority", response_model=CasePriorityListResponse)
def get_case_priority(
    priority_tier: str | None = Query(None, pattern="^(LOW|MEDIUM|HIGH)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    return store.case_priority_list(priority_tier=priority_tier, limit=limit)


@router.get("/case/{fir_id}", response_model=CasePriority)
def get_case(fir_id: str):
    result = store.case_detail(fir_id)
    if result is None:
        status = store.case_status_lookup(fir_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"fir_id '{fir_id}' not found")
        raise HTTPException(
            status_code=404,
            detail=f"fir_id '{fir_id}' has status '{status}' - not in the unresolved-case priority queue",
        )
    return result


@router.get("/person-dossier/{person_id}", response_model=PersonDossier)
def get_person_dossier(person_id: str):
    result = store.person_dossier(person_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"person_id '{person_id}' not found")
    return result


@router.get("/district-briefing/{district}", response_model=DistrictBriefing)
def get_district_briefing(district: str):
    result = store.district_briefing(district)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district '{district}' not found")
    return result
