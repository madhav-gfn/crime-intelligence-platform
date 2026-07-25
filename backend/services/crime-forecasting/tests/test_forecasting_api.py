import pytest
from fastapi.testclient import TestClient

from app.analytics_store import store
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
    assert r.json()["series_loaded"] == 1914


def test_stats(client):
    r = client.get("/api/forecasting/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_ncrb_districts"] == 827
    assert body["districts_with_complete_2001_2012_history"] == 638
    assert body["series_forecast"] == 638 * 3
    assert body["train_years"] == list(range(2001, 2010))
    assert body["test_years"] == [2010, 2011, 2012]
    assert body["forecast_years"] == [2013, 2014, 2015]
    assert sum(body["model_win_counts"].values()) == body["series_forecast"]


def test_district_forecast_found(client):
    r = client.get("/api/forecasting/district/CHENNAI")
    assert r.status_code == 200
    body = r.json()
    assert body["district"] == "CHENNAI"
    series_names = {s["series"] for s in body["series"]}
    assert series_names == {"TOTAL", "VIOLENT", "PROPERTY"}
    for s in body["series"]:
        assert s["selected_model"] in {"NAIVE", "LINEAR_TREND", "MOVING_AVERAGE"}
        # selected model must be the (tied-for-)lowest backtest MAE among the 3
        maes = [s["naive_backtest_mae"], s["linear_trend_backtest_mae"], s["moving_average_backtest_mae"]]
        assert s["backtest_mae"] == min(maes)


def test_district_forecast_not_found(client):
    r = client.get("/api/forecasting/district/NOT_A_REAL_DISTRICT_XYZ")
    assert r.status_code == 404


def test_district_forecast_substring_fallback(client):
    r = client.get("/api/forecasting/district/bangalore")
    assert r.status_code == 200
    assert "BANGALORE" in r.json()["district"]


def test_rankings_desc(client):
    r = client.get("/api/forecasting/rankings", params={"series": "TOTAL", "order": "desc", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["districts"]) == 10
    changes = [d["pct_change"] for d in body["districts"]]
    assert changes == sorted(changes, reverse=True)


def test_rankings_asc(client):
    r = client.get("/api/forecasting/rankings", params={"series": "VIOLENT", "order": "asc", "limit": 5})
    assert r.status_code == 200
    changes = [d["pct_change"] for d in r.json()["districts"]]
    assert changes == sorted(changes)


def test_rankings_invalid_series(client):
    r = client.get("/api/forecasting/rankings", params={"series": "NOT_A_SERIES"})
    assert r.status_code == 422


def test_all_series_have_full_backtest_history(client):
    r = client.get("/api/forecasting/district/DELHI")
    body = r.json()
    for s in body["series"]:
        assert s["last_observed_year"] == 2012
        assert s["forecast_2013"] >= 0
        assert s["forecast_2014"] >= 0
        assert s["forecast_2015"] >= 0
