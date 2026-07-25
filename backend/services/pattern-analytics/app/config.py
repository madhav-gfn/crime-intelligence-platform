from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via DATA_SEED_DIR env var, same convention as network-analysis.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"


settings = Settings()
