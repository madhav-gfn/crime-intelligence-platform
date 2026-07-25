"""
JWT verification + role-gating for this service. Literal copy of
backend/services/offender-profiling/app/rbac.py, not an import - each
service is deployed/versioned independently (own requirements.txt, own
venv), so there's no shared Python package to import from. See that
module's docstring, and backend/services/auth-service/README.md, for the
full rationale.

Roles, least to most access:
    ANALYST      - required for every endpoint in this service (baseline:
                   nothing here is served to an unauthenticated caller)
    INVESTIGATOR - required for anything naming a specific person (person
                   lookups, ego networks, hubs, repeat-offenders, paths) -
                   PII-adjacent. /stats is the only ANALYST-only endpoint.
    ADMIN        - implicitly satisfies INVESTIGATOR/ANALYST checks too
                   (see ROLE_RANK below)
"""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer_scheme = HTTPBearer(auto_error=True)

# Higher number = more access. A caller with a higher-ranked role than the
# minimum required always passes - so an ADMIN token works everywhere an
# INVESTIGATOR or ANALYST token would.
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
