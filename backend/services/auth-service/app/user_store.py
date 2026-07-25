"""
Loads the demo user store (data/processed/auth/users.json, bcrypt hashes
only - see scripts/data_generation/auth/build_demo_users.py) and keeps an
in-memory audit log of login attempts.

The audit log is in-memory and resets on restart - a known, documented
limitation (see README), not an oversight. A real deployment needs a
persistent, append-only audit store (governance requirements typically
mandate tamper-evidence, which an in-process Python list obviously isn't) -
this demonstrates the shape of audit logging (what gets recorded, who can
read it) without pretending to solve durable, tamper-evident storage in a
hackathon build.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.security import verify_password

MAX_AUDIT_LOG_ENTRIES = 1000


class UserStore:
    def __init__(self, users_path: Path):
        self.users_path = users_path
        self.users_by_username: dict[str, dict] = {}
        self.audit_log: list[dict] = []

    def load(self):
        raw = json.loads(self.users_path.read_text())
        self.users_by_username = {u["username"]: u for u in raw}
        self.audit_log = []
        return self

    def _log(self, event: str, username: str, success: bool, detail: str = ""):
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "username": username,
            "success": success,
            "detail": detail,
        })
        if len(self.audit_log) > MAX_AUDIT_LOG_ENTRIES:
            self.audit_log = self.audit_log[-MAX_AUDIT_LOG_ENTRIES:]

    def authenticate(self, username: str, password: str) -> dict | None:
        user = self.users_by_username.get(username)
        if user is None:
            self._log("LOGIN", username, False, "unknown username")
            return None
        if not verify_password(password, user["password_hash"]):
            self._log("LOGIN", username, False, "bad password")
            return None
        self._log("LOGIN", username, True)
        return user

    def get_user(self, username: str) -> dict | None:
        return self.users_by_username.get(username)

    def log_access_denied(self, username: str, required_roles: tuple[str, ...], path: str):
        self._log("ACCESS_DENIED", username, False, f"required one of {required_roles} for {path}")

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        return list(reversed(self.audit_log))[:limit]


store = UserStore(settings.users_path)
