from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via DATA_SEED_DIR env var - default assumes local monorepo
    # layout (backend/services/network-analysis -> ../../../data/seed).
    # In a Docker/Catalyst deployment this data would instead be pulled from
    # the Cloud Scale Data Store or a mounted volume; the env var is the seam.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"


settings = Settings()
