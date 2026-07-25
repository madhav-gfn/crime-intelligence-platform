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
    assert r.json()["accounts_loaded"] > 500_000


def test_stats_requires_auth(client):
    r = client.get("/api/financial/stats")
    assert r.status_code in (401, 403)


def test_stats(client):
    r = client.get("/api/financial/stats", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_accounts"] > 500_000
    assert body["total_transactions"] == 5_078_345
    assert body["ground_truth_laundering_transactions"] == 5_177
    assert set(body["risk_tier_counts"].keys()) <= {"LOW", "MEDIUM", "HIGH"}
    assert sum(body["risk_tier_counts"].values()) == body["total_accounts"]


def test_suspicious_accounts_requires_investigator(client):
    r = client.get("/api/financial/suspicious-accounts", headers=ANALYST_HEADERS)
    assert r.status_code == 403


def test_suspicious_accounts_high(client):
    r = client.get(
        "/api/financial/suspicious-accounts", params={"risk_tier": "HIGH", "limit": 10},
        headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["risk_tier"] == "HIGH"
    assert len(body["accounts"]) == 10
    for acct in body["accounts"]:
        assert acct["risk_tier"] == "HIGH"
        assert acct["risk_score"] >= 3
        # at least one rule must be the reason a HIGH account is HIGH
        assert any([
            acct["flag_high_fan_out"], acct["flag_high_fan_in"], acct["flag_rapid_passthrough"],
            acct["flag_cross_currency"], acct["flag_high_value_txn"],
        ])
    # sorted by risk_score descending
    scores = [a["risk_score"] for a in body["accounts"]]
    assert scores == sorted(scores, reverse=True)


def test_suspicious_accounts_invalid_tier(client):
    r = client.get(
        "/api/financial/suspicious-accounts", params={"risk_tier": "CRITICAL"}, headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 422


def test_account_profile_found(client):
    listing = client.get(
        "/api/financial/suspicious-accounts", params={"risk_tier": "HIGH", "limit": 1}, headers=INVESTIGATOR_HEADERS,
    ).json()
    account_id = listing["accounts"][0]["account_id"]
    r = client.get(f"/api/financial/account/{account_id}", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    assert r.json()["account_id"] == account_id


def test_account_profile_not_found(client):
    r = client.get("/api/financial/account/NOT_A_REAL_ACCOUNT_ID", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 404


def test_patterns_all(client):
    r = client.get("/api/financial/patterns", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_patterns"] == 370
    assert set(body["typologies"]) == {
        "BIPARTITE", "CYCLE", "FAN-IN", "FAN-OUT", "GATHER-SCATTER", "RANDOM", "SCATTER-GATHER", "STACK",
    }
    assert len(body["patterns"]) <= 50


def test_patterns_filtered_by_typology(client):
    r = client.get(
        "/api/financial/patterns", params={"typology": "FAN-OUT", "limit": 100}, headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_patterns"] == 48
    for p in body["patterns"]:
        assert p["typology"] == "FAN-OUT"
        assert p["n_transactions"] == len(p["transactions"])
        assert len(p["accounts_involved"]) >= 2


def test_path_direct_edge(client):
    edges = store.edges.iloc[0]
    r = client.get(
        "/api/financial/path", params={"source": edges["from_id"], "target": edges["to_id"]},
        headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["path"] == [edges["from_id"], edges["to_id"]]
    assert len(body["hops"]) == 1


def test_path_no_route(client):
    r = client.get(
        "/api/financial/path", params={"source": "NOT_REAL_A", "target": "NOT_REAL_B"},
        headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["found"] is False


def test_evaluate(client):
    r = client.get("/api/financial/evaluate", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["ground_truth_laundering_accounts"] == 6357
    # recall should improve (or at least not get worse) when the flagging
    # threshold is loosened from HIGH-only to MEDIUM+HIGH
    assert body["medium_or_high"]["recall"] >= body["high_only"]["recall"]
    for result in (body["high_only"], body["medium_or_high"]):
        assert 0.0 <= result["precision"] <= 1.0
        assert 0.0 <= result["recall"] <= 1.0
        assert 0.0 <= result["f1"] <= 1.0
