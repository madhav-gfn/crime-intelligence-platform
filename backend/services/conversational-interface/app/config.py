from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_DIR = Path(__file__).resolve().parents[1]
# In a deployed container the uploaded directory is flat (no backend/services/<name>
# nesting - see docs/deployment/DEPLOY.md), so this default is never actually reached
# there: every *_PATH/*_DIR field below is overridden via env var in that case. Falling
# back to _SERVICE_DIR keeps local dev (where the parents do go this deep) unchanged.
_REPO_ROOT = _SERVICE_DIR.parents[2] if len(_SERVICE_DIR.parents) >= 3 else _SERVICE_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8")

    # Only used to build the district-name entity index for NLU parsing
    # (see app/nlu.py) - not read for any analytics of its own.
    data_seed_dir: Path = _REPO_ROOT / "data" / "seed"

    # Base URLs of the downstream services this router forwards to. Unlike
    # every other cross-service consumer in this platform (which reads
    # precomputed files directly - see investigator-decision-support's and
    # explainable-ai's READMEs), this service makes live HTTP calls. That's
    # deliberate, not an inconsistency: a chat message can address any of
    # seven different analytics domains unpredictably, and duplicating each
    # of those services' full query/join logic here (the "literal copy"
    # pattern used for small things like rbac.py) would mean re-implementing
    # seven services' worth of real logic and keeping it all in sync by
    # hand. Delegating over HTTP means one source of truth per domain, at
    # the honest cost that this service degrades (not silently) if a
    # downstream service isn't running - see orchestrator.py.
    network_analysis_url: str = "http://localhost:8010"
    pattern_analytics_url: str = "http://localhost:8011"
    financial_crime_analysis_url: str = "http://localhost:8013"
    crime_forecasting_url: str = "http://localhost:8014"
    offender_profiling_url: str = "http://localhost:8016"
    investigator_decision_support_url: str = "http://localhost:8018"
    explainable_ai_url: str = "http://localhost:8021"

    downstream_timeout_seconds: float = 10.0

    # Must match auth-service's JWT_SECRET/JWT_ALGORITHM exactly - see
    # app/rbac.py's docstring for why tokens are verified statelessly here
    # rather than by calling back to auth-service per request. This
    # service's own gate is a floor only (ANALYST) - the caller's token is
    # forwarded as-is to whichever downstream service actually holds the
    # data, and that service's own RBAC is the real authorization decision
    # (see orchestrator.py / README).
    jwt_secret: str = "dev-only-insecure-secret-change-me-via-JWT_SECRET-env-var"
    jwt_algorithm: str = "HS256"


settings = Settings()
