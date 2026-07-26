"""
Per-session dialogue context: the deterministic, non-LLM stand-in for the
research doc's LangGraph "running context dictionary" of active case
numbers / suspect IDs. It does the one thing that dictionary is actually
for - resolving a follow-up like "what about his network?" to the person
last discussed - without requiring an LLM to do it.

**In-memory, resets on service restart** - a documented limitation, not an
oversight, same as auth-service's audit log. A real deployment would want
this backed by a shared store (Redis, a session table) so it survives
restarts and works across multiple app instances; this demo runs one
process.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    text: str
    intent: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    session_id: str
    last_person_id: str | None = None
    last_district: str | None = None
    history: list[Turn] = field(default_factory=list)


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        new_id = session_id or str(uuid.uuid4())
        session = Session(session_id=new_id)
        self._sessions[new_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)


sessions = SessionStore()
