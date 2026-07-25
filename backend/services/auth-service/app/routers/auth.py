from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_claims, require_role
from app.schemas import AuditLogResponse, LoginRequest, TokenResponse, UserOut
from app.security import create_access_token
from app.user_store import store

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = store.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid username or password")
    token, expires_in = create_access_token(user["username"], user["role"], user["full_name"])
    return {
        "access_token": token, "token_type": "bearer", "expires_in": expires_in,
        "role": user["role"], "full_name": user["full_name"],
    }


@router.get("/me", response_model=UserOut)
def me(claims: dict = Depends(get_current_claims)):
    user = store.get_user(claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="user no longer exists")
    return {
        "username": user["username"], "full_name": user["full_name"],
        "role": user["role"], "rank_context": user["rank_context"],
    }


@router.get("/audit-log", response_model=AuditLogResponse)
def audit_log(limit: int = 100, claims: dict = Depends(require_role("ADMIN"))):
    entries = store.get_audit_log(limit=limit)
    return {"count": len(entries), "entries": entries}
