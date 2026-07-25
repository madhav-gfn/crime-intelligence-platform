from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "financial-crime"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via *_PATH env vars, same convention as the other services.
    account_features_path: Path = _DATA_DIR / "account_features.csv"
    suspicious_edges_path: Path = _DATA_DIR / "suspicious_edges.csv"
    patterns_path: Path = _DATA_DIR / "laundering_patterns.json"
    eval_stats_path: Path = _DATA_DIR / "eval_stats.json"


settings = Settings()
