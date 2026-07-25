from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "offender-profiling"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    # Overridable via *_PATH env vars, same convention as the other services.
    person_scores_path: Path = _DATA_DIR / "person_risk_scores.csv"
    model_path: Path = _DATA_DIR / "model.pkl"
    feature_metadata_path: Path = _DATA_DIR / "feature_metadata.json"
    eval_stats_path: Path = _DATA_DIR / "eval_stats.json"
    # network-analysis / pattern-analytics's seed data, for the person profile join.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"


settings = Settings()
