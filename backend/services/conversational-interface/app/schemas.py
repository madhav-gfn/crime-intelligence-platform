from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    entities: dict[str, Any]
    downstream_service: str | None
    downstream_status: int | None
    data: Any = None


class TurnOut(BaseModel):
    role: str
    text: str
    intent: str | None
    timestamp: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    last_person_id: str | None
    last_district: str | None
    history: list[TurnOut]


class CapabilitiesResponse(BaseModel):
    description: str
    supported_intents: dict[str, str]
    note: str
