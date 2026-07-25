from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.analytics_store import store
from app.config import settings
from app.main import app


def _make_token(role: str, username: str = "test_user") -> str:
    payload = {
        "sub": username,
        "role": role,
        "full_name": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


ANALYST_HEADERS = {"Authorization": f"Bearer {_make_token('ANALYST')}"}
INVESTIGATOR_HEADERS = {"Authorization": f"Bearer {_make_token('INVESTIGATOR')}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {_make_token('ADMIN')}"}


@pytest.fixture(scope="module", autouse=True)
def loaded_store():
    store.load()
    yield store


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["persons_scored"] == 4746


def test_model_info_requires_auth(client):
    r = client.get("/api/offender-profiling/model-info")
    assert r.status_code in (401, 403)


def test_model_info_with_analyst_token(client):
    r = client.get("/api/offender-profiling/model-info", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["selected_model"] in {"LOGISTIC_REGRESSION", "RANDOM_FOREST"}
    assert set(body["model_comparison"].keys()) == {
        "LOGISTIC_REGRESSION", "RANDOM_FOREST", "BASELINE_PRIOR_CASE_RULE",
    }
    for name, m in body["model_comparison"].items():
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
        assert 0.0 <= m["f1"] <= 1.0
        if name != "BASELINE_PRIOR_CASE_RULE":
            assert 0.0 <= m["roc_auc"] <= 1.0
    assert sum(body["risk_tier_counts"].values()) == body["total_accused_persons_scored"]
    assert body["eligible_case_appearances"] < body["total_case_appearances"]  # some censored


def test_risk_list_analyst_forbidden(client):
    # ANALYST is below the INVESTIGATOR floor this endpoint requires
    r = client.get("/api/offender-profiling/risk-list", headers=ANALYST_HEADERS)
    assert r.status_code == 403


def test_risk_list_high_as_investigator(client):
    r = client.get(
        "/api/offender-profiling/risk-list", params={"risk_tier": "HIGH", "limit": 10},
        headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["risk_tier"] == "HIGH"
    assert len(body["persons"]) == 10
    probs = [p["predicted_reoffend_probability_365d"] for p in body["persons"]]
    assert probs == sorted(probs, reverse=True)
    for p in body["persons"]:
        assert p["risk_tier"] == "HIGH"


def test_risk_list_high_as_admin_also_works(client):
    # ADMIN outranks INVESTIGATOR - same floor should still pass
    r = client.get(
        "/api/offender-profiling/risk-list", params={"risk_tier": "HIGH", "limit": 1}, headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200


def test_risk_list_invalid_tier(client):
    r = client.get(
        "/api/offender-profiling/risk-list", params={"risk_tier": "CRITICAL"}, headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 422


def test_person_profile_found(client):
    listing = client.get(
        "/api/offender-profiling/risk-list", params={"risk_tier": "HIGH", "limit": 1}, headers=INVESTIGATOR_HEADERS,
    ).json()
    person_id = listing["persons"][0]["person_id"]
    r = client.get(f"/api/offender-profiling/person/{person_id}", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    assert r.json()["person_id"] == person_id


def test_person_profile_requires_investigator_not_just_analyst(client):
    r = client.get("/api/offender-profiling/person/ACC-000001", headers=ANALYST_HEADERS)
    assert r.status_code == 403


def test_person_profile_not_found(client):
    r = client.get("/api/offender-profiling/person/ACC-NOT-REAL", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 404


def test_predict_requires_investigator(client):
    r = client.get(
        "/api/offender-profiling/predict",
        params={"prior_case_count": 1, "distinct_prior_crime_types": 1, "age": 30},
        headers=ANALYST_HEADERS,
    )
    assert r.status_code == 403


def test_predict_high_risk_profile(client):
    r = client.get("/api/offender-profiling/predict", params={
        "prior_case_count": 15, "distinct_prior_crime_types": 5, "prior_violent_count": 5,
        "prior_property_count": 3, "days_since_first_case": 1200, "current_is_violent": True,
        "age": 30, "gender": "M", "state": "KARNATAKA",
    }, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["predicted_reoffend_probability_365d"] <= 1.0
    assert body["risk_tier"] in {"LOW", "MEDIUM", "HIGH"}


def test_predict_first_time_offender_scores_lower_than_repeat(client):
    common = {
        "distinct_prior_crime_types": 0, "prior_violent_count": 0, "prior_property_count": 0,
        "days_since_first_case": 0, "current_is_violent": False, "age": 30, "gender": "M", "state": "OTHER",
    }
    first_timer = client.get(
        "/api/offender-profiling/predict", params={**common, "prior_case_count": 0}, headers=INVESTIGATOR_HEADERS,
    ).json()
    repeat = client.get("/api/offender-profiling/predict", params={
        **common, "prior_case_count": 10, "distinct_prior_crime_types": 4, "prior_violent_count": 3,
        "days_since_first_case": 900,
    }, headers=INVESTIGATOR_HEADERS).json()
    assert repeat["predicted_reoffend_probability_365d"] > first_timer["predicted_reoffend_probability_365d"]


def test_predict_invalid_gender(client):
    r = client.get("/api/offender-profiling/predict", params={
        "prior_case_count": 1, "distinct_prior_crime_types": 1, "age": 30, "gender": "X",
    }, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 422


def test_expired_token_rejected(client):
    expired = jwt.encode(
        {
            "sub": "test_user", "role": "ADMIN",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    r = client.get("/api/offender-profiling/model-info", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_garbage_token_rejected(client):
    r = client.get("/api/offender-profiling/model-info", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401
