from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
# In a deployed container the uploaded directory is flat (no backend/services/<name>
# nesting - see docs/deployment/DEPLOY.md), so this default is never actually reached
# there: every *_PATH/*_DIR field below is overridden via env var in that case. Falling
# back to _SERVICE_DIR keeps local dev (where the parents do go this deep) unchanged.
_REPO_ROOT = _SERVICE_DIR.parents[2] if len(_SERVICE_DIR.parents) >= 3 else _SERVICE_DIR

# INSECURE by design - a fixed fallback so the service boots out of the box
# for local demo/dev without requiring env setup first. Any real deployment
# MUST set JWT_SECRET via env (see .env.example) - main.py logs a loud
# warning at startup if this default is still in use. Every other service
# that verifies tokens (see backend/services/offender-profiling/app/rbac.py)
# must be configured with the SAME secret - that's the actual mechanism
# that lets services verify tokens issued by this one without calling back
# to it per request (stateless JWT verification).
_INSECURE_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    users_path: Path = _REPO_ROOT / "data" / "processed" / "auth" / "users.json"
    jwt_secret: str = _INSECURE_DEV_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()
