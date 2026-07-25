from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.analytics_store import store
from app.config import settings
from app.main import app


def _make_token(role: str, username: str = "test_user") -> str:
    payload = {
        "sub": username, "role": role, "full_name": username,
        "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


ANALYST_HEADERS = {"Authorization": f"Bearer {_make_token('ANALYST')}"}
INVESTIGATOR_HEADERS = {"Authorization": f"Bearer {_make_token('INVESTIGATOR')}"}


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
    assert r.json()["persons_explained"] == 4746


def test_methodology_requires_auth(client):
    r = client.get("/api/explainability/methodology")
    assert r.status_code in (401, 403)


def test_methodology(client):
    r = client.get("/api/explainability/methodology", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    services = {p["service"] for p in body["pillars"]}
    assert services == {
        "network-analysis", "pattern-analytics", "sociological-insights",
        "financial-crime-analysis", "crime-forecasting", "offender-profiling",
        "investigator-decision-support",
    }


def test_model_info(client):
    r = client.get("/api/explainability/model-info", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_persons_explained"] == 4746
    assert body["max_reconstruction_error"] < 1e-6
    assert body["top_5_drivers"][0] == "prior_case_count"
    assert -1.0 <= body["concordance_with_rf_builtin_importance"]["value"] <= 1.0
    # every feature's mean |SHAP| must be non-negative
    assert all(v >= 0 for v in body["mean_abs_shap_by_feature"].values())


def test_person_explanation_requires_investigator(client):
    person_id = store.shap_values.index[0]
    r = client.get(f"/api/explainability/person/{person_id}", headers=ANALYST_HEADERS)
    assert r.status_code == 403


def test_person_explanation_found(client):
    person_id = store.shap_values.index[0]
    r = client.get(f"/api/explainability/person/{person_id}", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["person_id"] == person_id
    assert len(body["top_drivers"]) == 5
    assert len(body["all_contributions"]) == len(store.feature_names)
    # top_drivers must be the highest-|shap_value| entries from all_contributions,
    # in descending order of magnitude
    abs_values = [abs(c["shap_value"]) for c in body["all_contributions"]]
    assert abs_values == sorted(abs_values, reverse=True)
    # base_value + sum(all shap values) must reconstruct the actual predicted probability
    reconstructed = body["base_value"] + sum(c["shap_value"] for c in body["all_contributions"])
    assert abs(reconstructed - body["predicted_reoffend_probability_365d"]) < 1e-3


def test_person_explanation_not_found(client):
    r = client.get("/api/explainability/person/NOT_A_REAL_PERSON", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 404


def test_predict_explain_high_risk_profile(client):
    r = client.get(
        "/api/explainability/predict-explain",
        params={
            "prior_case_count": 8, "distinct_prior_crime_types": 4, "prior_violent_count": 3,
            "prior_property_count": 2, "days_since_first_case": 900, "current_is_violent": True,
            "current_is_property": False, "gender": "M", "age": 28, "state": "OTHER",
        },
        headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["predicted_reoffend_probability_365d"] <= 1.0
    assert body["risk_tier"] in {"LOW", "MEDIUM", "HIGH"}
    reconstructed = body["base_value"] + sum(c["shap_value"] for c in body["all_contributions"])
    assert abs(reconstructed - body["predicted_reoffend_probability_365d"]) < 1e-3
    # a high prior-case-count profile should have prior_case_count among its top drivers
    top_driver_names = {d["feature"] for d in body["top_drivers"]}
    assert "prior_case_count" in top_driver_names


def test_predict_explain_low_risk_profile(client):
    r = client.get(
        "/api/explainability/predict-explain",
        params={
            "prior_case_count": 0, "distinct_prior_crime_types": 0, "prior_violent_count": 0,
            "prior_property_count": 0, "days_since_first_case": 0, "current_is_violent": False,
            "current_is_property": False, "gender": "F", "age": 45, "state": "OTHER",
        },
        headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["predicted_reoffend_probability_365d"] < 0.5
