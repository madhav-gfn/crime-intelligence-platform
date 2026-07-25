"""
JWT verification + role-gating for this service. Literal copy of
backend/services/offender-profiling/app/rbac.py, not an import - see that
module's docstring, and backend/services/auth-service/README.md, for the
full rationale.

Roles, least to most access:
    ANALYST      - required for every endpoint (baseline: nothing here is
                   served to an unauthenticated caller). Sufficient for
                   /stats and /evaluate, which are dataset-wide aggregates.
    INVESTIGATOR - required for anything naming a specific account, entity,
                   or labeled-pattern example (/account/{id},
                   /suspicious-accounts, /patterns, /path) - account/entity
                   identifiers are the financial-crime equivalent of PII here.
    ADMIN        - implicitly satisfies INVESTIGATOR/ANALYST checks too
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
