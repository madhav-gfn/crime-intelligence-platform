from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    full_name: str


class UserOut(BaseModel):
    username: str
    full_name: str
    role: str
    rank_context: str


class AuditLogEntry(BaseModel):
    timestamp: str
    event: str
    username: str
    success: bool
    detail: str


class AuditLogResponse(BaseModel):
    count: int
    entries: list[AuditLogEntry]
