"""JWT issuance/verification and password checking. The verification half
(decode_token) is intentionally duplicated - not imported - into every
service that enforces RBAC, since they're deployed independently and each
needs to work without the auth-service being reachable at request time.
See backend/services/offender-profiling/app/rbac.py for that copy, and its
docstring for why a literal copy rather than a shared package, matching the
precedent set by taxonomy.py / crime_type_profiles.py elsewhere in this repo.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def create_access_token(username: str, role: str, full_name: str) -> tuple[str, int]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": username,
        "role": role,
        "full_name": full_name,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    expires_in = settings.access_token_expire_minutes * 60
    return token, expires_in


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (ExpiredSignatureError, InvalidTokenError, ...) on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
