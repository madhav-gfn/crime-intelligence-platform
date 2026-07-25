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
    assert r.json()["unresolved_cases_loaded"] == 1825


def test_stats(client):
    r = client.get("/api/decision-support/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_cases"] == 5000
    assert body["total_unresolved_cases"] == 1825
    assert sum(body["priority_tier_counts"].values()) == body["total_unresolved_cases"]
    assert body["stale_unresolved_case_count"] <= body["total_unresolved_cases"]


def test_case_priority_high(client):
    r = client.get("/api/decision-support/case-priority", params={"priority_tier": "HIGH", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["priority_tier"] == "HIGH"
    assert len(body["cases"]) == 10
    scores = [c["priority_score"] for c in body["cases"]]
    assert scores == sorted(scores, reverse=True)
    for c in body["cases"]:
        assert c["priority_score"] >= 6
        # score must equal the sum of its own components
        assert c["priority_score"] == (
            c["violent_points"] + c["accused_risk_points"] + c["hotspot_points"] + c["stale_points"]
        )


def test_case_priority_no_filter_returns_all_tiers(client):
    r = client.get("/api/decision-support/case-priority", params={"limit": 1000})
    tiers = {c["priority_tier"] for c in r.json()["cases"]}
    assert tiers <= {"LOW", "MEDIUM", "HIGH"}


def test_case_detail_found(client):
    listing = client.get("/api/decision-support/case-priority", params={"priority_tier": "HIGH", "limit": 1}).json()
    fir_id = listing["cases"][0]["fir_id"]
    r = client.get(f"/api/decision-support/case/{fir_id}")
    assert r.status_code == 200
    assert r.json()["fir_id"] == fir_id


def test_case_detail_not_found(client):
    r = client.get("/api/decision-support/case/NOT_A_REAL_FIR_ID")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_case_detail_resolved_case_gives_clear_message(client):
    # find a resolved (CONVICTED/CLOSED/ACQUITTED/CHARGESHEETED) fir_id
    resolved_fir_id = None
    for fir_id, status in zip(store.fir["fir_id"], store.fir["status"]):
        if status not in {"UNDER_INVESTIGATION", "TRIAL"}:
            resolved_fir_id = fir_id
            break
    assert resolved_fir_id is not None
    r = client.get(f"/api/decision-support/case/{resolved_fir_id}")
    assert r.status_code == 404
    assert "not in the unresolved-case priority queue" in r.json()["detail"]


def test_person_dossier_found(client):
    accused_person_id = store.link[store.link["role"] == "ACCUSED"]["person_id"].iloc[0]
    r = client.get(f"/api/decision-support/person-dossier/{accused_person_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["person_id"] == accused_person_id
    assert len(body["cases"]) >= 1
    assert body["offender_risk"] is not None
    assert body["offender_risk"]["risk_tier"] in {"LOW", "MEDIUM", "HIGH"}


def test_person_dossier_not_found(client):
    r = client.get("/api/decision-support/person-dossier/NOT_A_REAL_PERSON")
    assert r.status_code == 404


def test_district_briefing_found(client):
    r = client.get("/api/decision-support/district-briefing/CHENNAI")
    assert r.status_code == 200
    body = r.json()
    assert body["district"] == "CHENNAI"
    assert body["total_cases"] > 0
    assert 0.0 <= body["case_volume_percentile_rank"] <= 1.0
    # CHENNAI is high-volume, expect real socioeconomic/forecast matches
    assert body["socioeconomic"]["available"] is True
    assert body["forecast"]["available"] is True


def test_district_briefing_not_found(client):
    r = client.get("/api/decision-support/district-briefing/NOT_A_REAL_DISTRICT_XYZ")
    assert r.status_code == 404
