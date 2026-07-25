import bcrypt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import create_access_token
from app.user_store import store

TEST_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        # lifespan startup already ran store.load() - override the admin
        # user's hash with a known password so tests don't depend on the
        # random per-run demo passwords from the seed script
        store.users_by_username["admin"]["password_hash"] = bcrypt.hashpw(
            TEST_PASSWORD.encode(), bcrypt.gensalt()
        ).decode()
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["users_loaded"] >= 1


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "ADMIN"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert len(body["access_token"]) > 20


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "not_a_real_user", "password": "x"})
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)  # HTTPBearer rejects a missing Authorization header


def test_me_with_valid_token(client):
    login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}).json()
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "ADMIN"


def test_me_with_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_audit_log_requires_admin(client):
    # analyst-role token should NOT be able to read the audit log
    token, _ = create_access_token("some_analyst", "ANALYST", "Some Analyst")
    r = client.get("/api/auth/audit-log", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_audit_log_as_admin_includes_recent_events(client):
    client.post("/api/auth/login", json={"username": "admin", "password": "wrong-on-purpose"})
    login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}).json()
    r = client.get("/api/auth/audit-log", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    events = [e["event"] for e in body["entries"]]
    assert "LOGIN" in events
    # failed login attempt should be recorded
    assert any(e["event"] == "LOGIN" and not e["success"] for e in body["entries"])
