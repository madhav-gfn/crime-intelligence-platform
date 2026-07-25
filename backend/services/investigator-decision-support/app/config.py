from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via *_PATH / *_DIR env vars, same convention as the other services.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"
    offender_risk_path: Path = _REPO_ROOT / "data" / "processed" / "offender-profiling" / "person_risk_scores.csv"
    district_forecasts_path: Path = _REPO_ROOT / "data" / "processed" / "forecasting" / "district_forecasts.csv"
    district_socioeconomic_path: Path = (
        _REPO_ROOT / "data" / "processed" / "sociology" / "district_socioeconomic_crime.csv"
    )

    stale_case_days: int = 180


settings = Settings()
