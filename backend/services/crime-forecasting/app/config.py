from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "forecasting"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # Overridable via *_PATH env vars, same convention as the other services.
    forecasts_path: Path = _DATA_DIR / "district_forecasts.csv"
    forecast_stats_path: Path = _DATA_DIR / "forecast_stats.json"

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request.
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
