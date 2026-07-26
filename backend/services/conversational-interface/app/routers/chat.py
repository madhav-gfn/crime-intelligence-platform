from fastapi import APIRouter, Depends, HTTPException, Request

from app.nlu import parse
from app.orchestrator import CAPABILITIES
from app.rbac import require_role
from app.schemas import CapabilitiesResponse, ChatRequest, ChatResponse, SessionHistoryResponse, TurnOut
from app.session_store import Turn, sessions

router = APIRouter(prefix="/api/chat", tags=["conversational-interface"])


@router.post("/message", response_model=ChatResponse)
async def post_message(
    body: ChatRequest, request: Request, claims: dict = Depends(require_role("ANALYST")),
):
    session = sessions.get_or_create(body.session_id)
    parsed = parse(body.message, request.app.state.district_index)
    session.history.append(Turn(role="user", text=body.message, intent=parsed.intent))

    auth_header = request.headers.get("authorization", "")
    result = await request.app.state.orchestrator.answer(parsed, session, auth_header)

    session.history.append(Turn(role="assistant", text=result["reply"], intent=parsed.intent))

    return ChatResponse(
        session_id=session.session_id,
        reply=result["reply"],
        intent=result["intent"],
        entities=parsed.raw_entities,
        downstream_service=result["downstream_service"],
        downstream_status=result["downstream_status"],
        data=result["data"],
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities(claims: dict = Depends(require_role("ANALYST"))):
    return CapabilitiesResponse(
        description=(
            "Deterministic, rule-based query router over this platform's analytics services - "
            "not an LLM. Understands a fixed set of question shapes (see supported_intents), not "
            "open-ended free text."
        ),
        supported_intents=CAPABILITIES,
        note=(
            "No LLM API key is available in this environment, so intent classification and entity "
            "extraction are regex/keyword-based (see app/nlu.py), not model-based. Multi-turn "
            "follow-ups ('what about his network?') resolve via a per-session context dictionary "
            "(app/session_store.py), the same role the research doc's LangGraph state graph plays, "
            "implemented deterministically instead of with an LLM."
        ),
    )


@router.get("/session/{session_id}/history", response_model=SessionHistoryResponse)
def get_session_history(session_id: str, claims: dict = Depends(require_role("ANALYST"))):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session_id '{session_id}' not found")
    return SessionHistoryResponse(
        session_id=session.session_id,
        last_person_id=session.last_person_id,
        last_district=session.last_district,
        history=[TurnOut(role=t.role, text=t.text, intent=t.intent, timestamp=t.timestamp) for t in session.history],
    )
