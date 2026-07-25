from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # Overridable via DISTRICT_DATA_PATH / MATCH_STATS_PATH env vars.
    district_data_path: Path = (
        _REPO_ROOT / "data" / "processed" / "sociology" / "district_socioeconomic_crime.csv"
    )
    match_stats_path: Path = _REPO_ROOT / "data" / "processed" / "sociology" / "match_stats.json"

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request.
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
