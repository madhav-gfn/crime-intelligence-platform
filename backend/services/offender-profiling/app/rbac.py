"""
JWT verification + role-gating for this service, applied as a concrete,
fully-tested demonstration of pillar 10 (secure RBAC/governance) - see
backend/services/auth-service/README.md for the full rationale and the
other six services this same pattern still needs to be copied into.

This is a literal copy of the verification half of
backend/services/auth-service/app/security.py's decode_token, not an
import - each service is deployed and versioned independently (own
requirements.txt, own venv), so there's no shared Python package to import
from without adding a real dependency-management mechanism this repo
doesn't have yet. That's the same tradeoff already made for
VIOLENT_TYPES/PROPERTY_TYPES across pattern-analytics/crime-forecasting/
investigator-decision-support - see those modules' docstrings for the same
precedent. What actually keeps the two services in sync is the shared
JWT_SECRET/JWT_ALGORITHM env vars, not shared code - this service can
verify a token auth-service issued without ever calling auth-service at
request time (stateless verification, the standard JWT microservices
pattern).

Roles, least to most access:
    ANALYST      - required for every endpoint in this service (baseline:
                   nothing here is served to an unauthenticated caller)
    INVESTIGATOR - required for anything that names a specific person
                   (person profile, risk-list, predict) - PII-adjacent
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
