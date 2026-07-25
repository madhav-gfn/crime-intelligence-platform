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
    assert r.json()["firs_loaded"] == 5000


def test_stats_requires_auth(client):
    r = client.get("/api/patterns/stats")
    assert r.status_code in (401, 403)


def test_stats(client):
    r = client.get("/api/patterns/stats", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_firs"] == 5000
    assert body["distinct_crime_types"] == 21
    assert sum(body["crime_type_counts"].values()) == 5000


def test_hotspots_default(client):
    r = client.get(
        "/api/patterns/hotspots", params={"crime_type": "THEFT", "eps_km": 15, "min_points": 4},
        headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_points_considered"] > 0
    assert len(body["clusters"]) > 0
    top = body["clusters"][0]
    assert top["point_count"] >= body["min_points"]
    assert 0.0 <= top["geo_precise_fraction"] <= 1.0
    # clusters should be sorted by size descending
    sizes = [c["point_count"] for c in body["clusters"]]
    assert sizes == sorted(sizes, reverse=True)


def test_hotspots_empty_when_too_few_points(client):
    r = client.get(
        "/api/patterns/hotspots", params={"crime_type": "DACOITY", "min_points": 500}, headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["clusters"] == []


def test_district_severity(client):
    r = client.get("/api/patterns/district-severity", params={"min_crimes": 10}, headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["districts_included"] > 0
    tiers_seen = {t["severity_tier"] for t in body["tiers"]}
    assert tiers_seen <= {"LOW", "MEDIUM", "HIGH"}
    # districts below the min_crimes threshold must not appear
    assert all(t["total_crimes"] >= 10 for t in body["tiers"])
    # a known high-volume district should land in HIGH
    bangalore = next(t for t in body["tiers"] if t["district"] == "BANGALORE COMMR.")
    assert bangalore["severity_tier"] == "HIGH"


@pytest.mark.parametrize("granularity,expected_buckets", [("weekday", 7), ("hourly", 24)])
def test_trends_fixed_bucket_counts(client, granularity, expected_buckets):
    r = client.get(f"/api/patterns/trends/{granularity}", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == expected_buckets
    assert sum(p["count"] for p in body["points"]) == 5000


def test_trends_monthly_covers_full_range(client):
    r = client.get("/api/patterns/trends/monthly", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    points = r.json()["points"]
    assert points[0]["bucket"] == "2020-01"
    assert points[-1]["bucket"] == "2024-12"


def test_trends_invalid_granularity_400(client):
    r = client.get("/api/patterns/trends/yearly", headers=ANALYST_HEADERS)
    assert r.status_code == 400


def test_trends_filter_by_crime_type_reduces_count(client):
    r_all = client.get("/api/patterns/trends/weekday", headers=ANALYST_HEADERS)
    r_theft = client.get(
        "/api/patterns/trends/weekday", params={"crime_type": "THEFT"}, headers=ANALYST_HEADERS,
    )
    total_all = sum(p["count"] for p in r_all.json()["points"])
    total_theft = sum(p["count"] for p in r_theft.json()["points"])
    assert 0 < total_theft < total_all


def test_emerging(client):
    r = client.get(
        "/api/patterns/emerging", params={"recent_days": 180, "baseline_days": 365, "min_recent_count": 3},
        headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    for alert in body["alerts"]:
        assert alert["recent_count"] >= 3
        if alert["pct_change"] is not None:
            assert alert["pct_change"] >= 50


def test_similar_cases(client, loaded_store):
    sample_fir_id = loaded_store.df.iloc[0]["fir_id"]
    r = client.get(
        f"/api/patterns/similar-cases/{sample_fir_id}", params={"top_n": 5}, headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source_fir_id"] == sample_fir_id
    assert len(body["results"]) == 5
    # results should never include the source case itself
    assert all(res["fir_id"] != sample_fir_id for res in body["results"])
    # sorted by similarity descending
    sims = [res["similarity"] for res in body["results"]]
    assert sims == sorted(sims, reverse=True)


def test_similar_cases_404(client):
    r = client.get("/api/patterns/similar-cases/NOT-A-REAL-FIR", headers=ANALYST_HEADERS)
    assert r.status_code == 404
