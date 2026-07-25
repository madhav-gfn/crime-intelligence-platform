from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "financial-crime"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # Overridable via *_PATH env vars, same convention as the other services.
    account_features_path: Path = _DATA_DIR / "account_features.csv"
    suspicious_edges_path: Path = _DATA_DIR / "suspicious_edges.csv"
    patterns_path: Path = _DATA_DIR / "laundering_patterns.json"
    eval_stats_path: Path = _DATA_DIR / "eval_stats.json"

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request.
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
