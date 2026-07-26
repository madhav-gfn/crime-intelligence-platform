from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
# In a deployed container the uploaded directory is flat (no backend/services/<name>
# nesting - see docs/deployment/DEPLOY.md), so this default is never actually reached
# there: every *_PATH/*_DIR field below is overridden via env var in that case. Falling
# back to _SERVICE_DIR keeps local dev (where the parents do go this deep) unchanged.
_REPO_ROOT = _SERVICE_DIR.parents[2] if len(_SERVICE_DIR.parents) >= 3 else _SERVICE_DIR

_DATA_DIR = _REPO_ROOT / "data" / "processed" / "offender-profiling"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # Overridable via *_PATH env vars, same convention as the other services.
    person_scores_path: Path = _DATA_DIR / "person_risk_scores.csv"
    model_path: Path = _DATA_DIR / "model.pkl"
    feature_metadata_path: Path = _DATA_DIR / "feature_metadata.json"
    eval_stats_path: Path = _DATA_DIR / "eval_stats.json"
    # network-analysis / pattern-analytics's seed data, for the person profile join.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request.
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
