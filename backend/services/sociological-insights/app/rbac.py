"""
JWT verification + role-gating for this service. Literal copy of
backend/services/offender-profiling/app/rbac.py, not an import - see that
module's docstring, and backend/services/auth-service/README.md, for the
full rationale.

This service is district-level aggregate data only (census statistics
joined against crime rates) - no person-level data exists anywhere in this
service's output, so every endpoint only requires the `ANALYST` floor.
"""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer_scheme = HTTPBearer(auto_error=True)

ROLE_RANK = {"ANALYST": 1, "INVESTIGATOR": 2, "ADMIN": 3}


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_current_claims(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> dict:
    try:
        return _decode(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")


def require_role(minimum_role: str):
    minimum_rank = ROLE_RANK[minimum_role]

    def _check(claims: dict = Depends(get_current_claims)) -> dict:
        role = claims.get("role")
        if ROLE_RANK.get(role, 0) < minimum_rank:
            raise HTTPException(status_code=403, detail=f"requires role '{minimum_role}' or higher")
        return claims
    return _check
