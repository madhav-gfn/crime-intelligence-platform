from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.orchestrator import Orchestrator
from app.session_store import sessions


def _make_token(role: str, username: str = "test_user") -> str:
    payload = {
        "sub": username, "role": role, "full_name": username,
        "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


ANALYST_HEADERS = {"Authorization": f"Bearer {_make_token('ANALYST')}"}

PERSON_DOSSIER_JSON = {
    "person_id": "ACC-002543", "full_name": "Ravi Kumar", "gender": "M", "age": 34,
    "address_district": "BIDAR", "address_state": "KARNATAKA",
    "offender_risk": {
        "prior_case_count": 5, "distinct_crime_types_count": 2,
        "predicted_reoffend_probability_365d": 0.72, "risk_tier": "HIGH",
    },
    "network_degree": 3, "top_associates": [], "cases": [],
}

PERSON_EXPLANATION_JSON = {
    "person_id": "ACC-002543", "full_name": "Ravi Kumar", "risk_tier": "HIGH",
    "predicted_reoffend_probability_365d": 0.72, "base_value": 0.5, "reconstruction_error": 1e-9,
    "top_drivers": [{"feature": "prior_case_count", "shap_value": 0.15, "feature_value": 5.0}],
    "all_contributions": [{"feature": "prior_case_count", "shap_value": 0.15, "feature_value": 5.0}],
}

FORBIDDEN_JSON = {"detail": "requires role 'INVESTIGATOR' or higher"}


def _mock_transport(responses: dict[str, httpx.Response], unreachable_paths: set[str] = frozenset()):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in unreachable_paths:
            raise httpx.ConnectError("connection refused", request=request)
        if path in responses:
            return responses[path]
        return httpx.Response(404, json={"detail": f"not mocked: {path}"})
    return httpx.MockTransport(handler)


@pytest.fixture
def client():
    with TestClient(app) as c:
        sessions._sessions.clear()
        yield c


def _install_mock(client, responses: dict[str, httpx.Response], unreachable_paths: set[str] = frozenset()):
    mock_client = httpx.AsyncClient(transport=_mock_transport(responses, unreachable_paths))
    client.app.state.http_client = mock_client
    client.app.state.orchestrator = Orchestrator(mock_client, settings)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_capabilities_requires_auth(client):
    r = client.get("/api/chat/capabilities")
    assert r.status_code in (401, 403)


def test_capabilities_content(client):
    r = client.get("/api/chat/capabilities", headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "person_dossier" in body["supported_intents"]
    assert "llm" in body["note"].lower()


def test_help_intent_makes_no_downstream_call(client):
    _install_mock(client, {})
    r = client.post("/api/chat/message", json={"message": "help"}, headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "help"
    assert body["downstream_service"] is None
    assert "session_id" in body


def test_unknown_intent(client):
    _install_mock(client, {})
    r = client.post("/api/chat/message", json={"message": "asdkjaslkdj random gibberish"}, headers=ANALYST_HEADERS)
    assert r.status_code == 200
    assert r.json()["intent"] == "unknown"


def test_person_dossier_missing_entity_asks_for_clarification(client):
    _install_mock(client, {})
    r = client.post("/api/chat/message", json={"message": "who is this person"}, headers=ANALYST_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "person_dossier"
    assert body["downstream_service"] is None
    assert "person id" in body["reply"].lower() or "which person" in body["reply"].lower()


def test_person_dossier_success(client):
    _install_mock(client, {
        "/api/decision-support/person-dossier/ACC-002543": httpx.Response(200, json=PERSON_DOSSIER_JSON),
    })
    r = client.post(
        "/api/chat/message", json={"message": "who is ACC-002543"}, headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "person_dossier"
    assert body["downstream_service"] == "investigator-decision-support"
    assert body["downstream_status"] == 200
    assert "Ravi Kumar" in body["reply"]
    assert "HIGH" in body["reply"]
    assert body["entities"]["person_id"] == "ACC-002543"
    assert body["data"]["person_id"] == "ACC-002543"


def test_pronoun_resolution_across_turns(client):
    _install_mock(client, {
        "/api/decision-support/person-dossier/ACC-002543": httpx.Response(200, json=PERSON_DOSSIER_JSON),
        "/api/explainability/person/ACC-002543": httpx.Response(200, json=PERSON_EXPLANATION_JSON),
    })
    r1 = client.post(
        "/api/chat/message", json={"message": "tell me about ACC-002543"}, headers=ANALYST_HEADERS,
    )
    session_id = r1.json()["session_id"]

    r2 = client.post(
        "/api/chat/message",
        json={"message": "why is he high risk", "session_id": session_id},
        headers=ANALYST_HEADERS,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["intent"] == "person_explain"
    assert body["entities"]["person_id"] is None  # no explicit ID in turn 2 - resolved from context
    assert body["data"]["person_id"] == "ACC-002543"
    assert body["downstream_status"] == 200


def test_downstream_403_propagates_honestly(client):
    _install_mock(client, {
        "/api/decision-support/person-dossier/ACC-002543": httpx.Response(403, json=FORBIDDEN_JSON),
    })
    r = client.post(
        "/api/chat/message", json={"message": "who is ACC-002543"}, headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200  # the chat endpoint itself succeeds; the *downstream* call was denied
    body = r.json()
    assert body["downstream_status"] == 403
    assert "access denied" in body["reply"].lower()
    assert body["data"] is None


def test_downstream_unreachable(client):
    _install_mock(
        client, {}, unreachable_paths={"/api/decision-support/person-dossier/ACC-002543"},
    )
    r = client.post(
        "/api/chat/message", json={"message": "who is ACC-002543"}, headers=ANALYST_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["downstream_status"] is None
    assert "isn't reachable" in body["reply"].lower()


def test_session_history_not_found(client):
    r = client.get("/api/chat/session/not-a-real-session/history", headers=ANALYST_HEADERS)
    assert r.status_code == 404


def test_session_history_records_turns(client):
    _install_mock(client, {
        "/api/decision-support/person-dossier/ACC-002543": httpx.Response(200, json=PERSON_DOSSIER_JSON),
    })
    r1 = client.post(
        "/api/chat/message", json={"message": "who is ACC-002543"}, headers=ANALYST_HEADERS,
    )
    session_id = r1.json()["session_id"]

    r2 = client.get(f"/api/chat/session/{session_id}/history", headers=ANALYST_HEADERS)
    assert r2.status_code == 200
    body = r2.json()
    assert body["last_person_id"] == "ACC-002543"
    assert len(body["history"]) == 2  # one user turn, one assistant turn
