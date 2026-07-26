"""
JWT verification + role-gating for this service - see
backend/services/auth-service/README.md for the full RBAC rationale.

This is a literal copy of the verification half of
backend/services/auth-service/app/security.py's decode_token, not an
import - each service is deployed and versioned independently (own
requirements.txt, own venv), so there's no shared Python package to import
from without adding a real dependency-management mechanism this repo
doesn't have yet. Same tradeoff as every other service's app/rbac.py.

This service only gates its own entry point at the ANALYST floor -
`/api/chat/message` forwards the caller's own token unchanged to whichever
downstream service actually answers the question, and that service makes
the real INVESTIGATOR/ADMIN decision (see orchestrator.py). So this
router.py never needs a higher minimum_role than ANALYST anywhere.
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
