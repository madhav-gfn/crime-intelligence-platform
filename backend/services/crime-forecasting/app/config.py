from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "forecasting"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via *_PATH env vars, same convention as the other services.
    forecasts_path: Path = _DATA_DIR / "district_forecasts.csv"
    forecast_stats_path: Path = _DATA_DIR / "forecast_stats.json"


settings = Settings()
