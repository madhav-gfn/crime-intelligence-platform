from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parents[2]

_EXPLAIN_DIR = _REPO_ROOT / "data" / "processed" / "explainability"
_OFFENDER_DIR = _REPO_ROOT / "data" / "processed" / "offender-profiling"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # This service's own precomputed outputs (see
    # scripts/data_generation/explainability/build_shap_explanations.py).
    shap_values_path: Path = _EXPLAIN_DIR / "shap_values.csv"
    global_importance_path: Path = _EXPLAIN_DIR / "global_importance.json"

    # Read directly from offender-profiling's own processed outputs, same
    # tradeoff investigator-decision-support makes (see that service's
    # README) - not a live HTTP call, and not a duplicated copy of the
    # model file either: single source of truth for the actual classifier.
    model_path: Path = _OFFENDER_DIR / "model.pkl"
    feature_metadata_path: Path = _OFFENDER_DIR / "feature_metadata.json"
    person_scores_path: Path = _OFFENDER_DIR / "person_risk_scores.csv"
    person_feature_vectors_path: Path = _OFFENDER_DIR / "person_feature_vectors.csv"
    offender_eval_stats_path: Path = _OFFENDER_DIR / "eval_stats.json"

    # For readable person lookups (full_name/district), same join
    # offender-profiling itself performs.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request.
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
