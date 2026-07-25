from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.graph_store import store
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
    assert r.json()["nodes_loaded"] > 0


def test_stats_requires_auth(client):
    r = client.get("/api/network/stats")
    assert r.status_code in (401, 403)


def test_stats(client):
    r = client.get("/api/network/stats", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_persons_in_network"] > 0
    assert body["total_edges"] > 0
    assert body["total_firs"] == 5000


def test_graph_requires_investigator_not_just_analyst(client):
    r = client.get("/api/network/graph", headers=ANALYST_HEADERS)
    assert r.status_code == 403


def test_graph_default(client):
    r = client.get("/api/network/graph", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["node_count"] == len(body["nodes"])
    assert body["edge_count"] == len(body["edges"])
    assert body["node_count"] <= 300  # default limit_nodes


def test_graph_min_shared_cases_filters(client):
    r_all = client.get(
        "/api/network/graph", params={"min_shared_cases": 1, "limit_nodes": 5000}, headers=INVESTIGATOR_HEADERS,
    )
    r_strong = client.get(
        "/api/network/graph", params={"min_shared_cases": 3, "limit_nodes": 5000}, headers=INVESTIGATOR_HEADERS,
    )
    assert r_strong.json()["edge_count"] <= r_all.json()["edge_count"]


def test_hubs_sorted_by_degree(client):
    r = client.get("/api/network/hubs", params={"top_n": 10}, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    hubs = r.json()
    assert len(hubs) == 10
    degrees = [h["degree"] for h in hubs]
    assert degrees == sorted(degrees, reverse=True)


def test_person_lookup_and_404(client, loaded_store):
    top_hub = client.get("/api/network/hubs", params={"top_n": 1}, headers=INVESTIGATOR_HEADERS).json()[0]
    pid = top_hub["person_id"]

    r = client.get(f"/api/network/person/{pid}", headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    assert r.json()["person_id"] == pid

    r_missing = client.get("/api/network/person/NOT-A-REAL-ID", headers=INVESTIGATOR_HEADERS)
    assert r_missing.status_code == 404


def test_ego_network(client):
    top_hub = client.get("/api/network/hubs", params={"top_n": 1}, headers=INVESTIGATOR_HEADERS).json()[0]
    pid = top_hub["person_id"]

    r = client.get(f"/api/network/person/{pid}/ego", params={"depth": 1}, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["center"]["person_id"] == pid
    assert len(body["nodes"]) >= 2  # center + at least one neighbor for a hub


def test_communities_meet_min_size(client):
    r = client.get("/api/network/communities", params={"min_size": 3}, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    communities = r.json()
    assert all(c["size"] >= 3 for c in communities)
    if communities:
        assert communities == sorted(communities, key=lambda c: -c["size"])


def test_path_between_connected_nodes(client, loaded_store):
    top_hub = client.get("/api/network/hubs", params={"top_n": 1}, headers=INVESTIGATOR_HEADERS).json()[0]
    a = top_hub["person_id"]
    b = next(iter(loaded_store.graph.neighbors(a)))

    r = client.get("/api/network/path", params={"source": a, "target": b}, headers=INVESTIGATOR_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["path"][0] == a
    assert body["path"][-1] == b
    assert len(body["hops"]) == 1  # direct neighbors -> single hop


def test_path_unknown_person_404(client):
    r = client.get(
        "/api/network/path", params={"source": "NOPE", "target": "ALSO-NOPE"}, headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 404


def test_repeat_offenders(client):
    r = client.get(
        "/api/network/repeat-offenders", params={"min_cases": 2, "limit": 10}, headers=INVESTIGATOR_HEADERS,
    )
    assert r.status_code == 200
    rows = r.json()
    assert all(row["prior_case_count"] >= 2 for row in rows)
    counts = [row["prior_case_count"] for row in rows]
    assert counts == sorted(counts, reverse=True)
