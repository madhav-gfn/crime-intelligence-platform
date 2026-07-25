from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via DISTRICT_DATA_PATH / MATCH_STATS_PATH env vars.
    district_data_path: Path = (
        _REPO_ROOT / "data" / "processed" / "sociology" / "district_socioeconomic_crime.csv"
    )
    match_stats_path: Path = _REPO_ROOT / "data" / "processed" / "sociology" / "match_stats.json"


settings = Settings()
