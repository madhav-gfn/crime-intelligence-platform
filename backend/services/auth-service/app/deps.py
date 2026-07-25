import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security import decode_token
from app.user_store import store

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_claims(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> dict:
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")


def require_role(*roles: str):
    def _check(request: Request, claims: dict = Depends(get_current_claims)) -> dict:
        if claims.get("role") not in roles:
            store.log_access_denied(claims.get("sub", "unknown"), roles, request.url.path)
            raise HTTPException(status_code=403, detail=f"requires one of roles: {roles}")
        return claims
    return _check
