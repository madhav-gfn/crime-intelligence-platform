import pytest
from fastapi.testclient import TestClient

from app.analytics_store import ALLOWED_INDICATORS, CRIME_METRICS, DEMOGRAPHIC_CONTEXT_ONLY, store
from app.main import app


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
    assert r.json()["districts_loaded"] > 0


def test_districts_list(client):
    r = client.get("/api/sociology/districts")
    assert r.status_code == 200
    body = r.json()
    assert body["matched_districts"] > 0
    assert body["total_census_districts"] >= body["matched_districts"]
    assert 0.0 < body["match_rate"] <= 1.0
    assert len(body["districts"]) == body["matched_districts"]
    # sorted by crime_rate_per_100k descending
    rates = [d["crime_rate_per_100k"] for d in body["districts"]]
    assert rates == sorted(rates, reverse=True)


def test_district_profile_found(client):
    listing = client.get("/api/sociology/districts").json()
    sample = listing["districts"][0]["district"]
    r = client.get(f"/api/sociology/district/{sample}")
    assert r.status_code == 200
    body = r.json()
    assert body["district"].lower() == sample.lower() or sample.lower() in body["district"].lower()
    for field in DEMOGRAPHIC_CONTEXT_ONLY:
        assert field in body  # present as context...
    for field in ALLOWED_INDICATORS:
        assert field in body


def test_district_profile_not_found(client):
    r = client.get("/api/sociology/district/ZZZ_NOT_A_REAL_DISTRICT")
    assert r.status_code == 404


def test_correlations_excludes_demographic_fields(client):
    r = client.get("/api/sociology/correlations")
    assert r.status_code == 200
    body = r.json()
    assert body["indicators_used"] == ALLOWED_INDICATORS
    used_indicators = {res["indicator"] for res in body["results"]}
    # ...but never appear as a correlated indicator
    assert used_indicators.isdisjoint(DEMOGRAPHIC_CONTEXT_ONLY)
    assert used_indicators.issubset(set(ALLOWED_INDICATORS))
    for res in body["results"]:
        assert res["crime_metric"] in CRIME_METRICS
        assert -1.0 <= res["pearson_r"] <= 1.0
        assert res["n"] >= 10


def test_correlations_min_population_filter(client):
    r_all = client.get("/api/sociology/correlations")
    r_filtered = client.get("/api/sociology/correlations", params={"min_population": 2_000_000})
    assert r_filtered.status_code == 200
    assert r_filtered.json()["districts_included"] < r_all.json()["districts_included"]


def test_rankings_valid_field(client):
    r = client.get("/api/sociology/rankings", params={"sort_by": "literacy_rate", "order": "desc", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert len(body["districts"]) == 5
    values = [d["value"] for d in body["districts"]]
    assert values == sorted(values, reverse=True)


def test_rankings_ascending(client):
    r = client.get("/api/sociology/rankings", params={"sort_by": "crime_rate_per_100k", "order": "asc", "limit": 5})
    assert r.status_code == 200
    values = [d["value"] for d in r.json()["districts"]]
    assert values == sorted(values)


def test_rankings_rejects_demographic_field(client):
    r = client.get("/api/sociology/rankings", params={"sort_by": "sc_st_share"})
    assert r.status_code == 400


def test_rankings_rejects_unknown_field(client):
    r = client.get("/api/sociology/rankings", params={"sort_by": "not_a_real_column"})
    assert r.status_code == 400


def test_scatter_valid(client):
    r = client.get("/api/sociology/scatter/literacy_rate", params={"crime_metric": "crime_rate_per_100k"})
    assert r.status_code == 200
    body = r.json()
    assert body["indicator"] == "literacy_rate"
    assert len(body["points"]) > 0


def test_scatter_rejects_demographic_indicator(client):
    r = client.get("/api/sociology/scatter/muslim_share")
    assert r.status_code == 400


def test_scatter_rejects_bad_crime_metric(client):
    r = client.get("/api/sociology/scatter/literacy_rate", params={"crime_metric": "not_a_metric"})
    assert r.status_code == 400
