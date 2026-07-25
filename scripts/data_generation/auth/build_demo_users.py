"""
Generates the demo user store for auth-service (pillar 10). Only bcrypt
password hashes are ever written to disk - plaintext demo passwords are
printed to stdout once, at generation time, and nowhere else. This mirrors
the "prep script produces an artifact, service loads the artifact" pattern
used by every other pillar, and data/processed/ is already gitignored
repo-wide, so this never risks landing in git even as a "just a demo"
credential.

Roles (see backend/services/auth-service/README.md for the full RBAC
rationale):
    ANALYST      - aggregate/statistical endpoints only
    INVESTIGATOR - adds person/case/account-level (PII-adjacent) access
    ADMIN        - full access, including the audit log

Usage:
    python scripts/data_generation/auth/build_demo_users.py
"""
import json
import secrets
import string
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = ROOT / "data" / "processed" / "auth" / "users.json"

# (username, full_name, role, rank_context) - rank_context is flavor text
# only, not used for access control (role is the only thing that matters).
DEMO_USERS = [
    ("admin", "Admin User", "ADMIN", "System Administrator"),
    ("sp_reddy", "K. Reddy", "ADMIN", "Superintendent of Police"),
    ("pi_sharma", "R. Sharma", "INVESTIGATOR", "Police Inspector"),
    ("si_verma", "A. Verma", "INVESTIGATOR", "Sub-Inspector"),
    ("analyst_iyer", "S. Iyer", "ANALYST", "Crime Analytics Unit"),
    ("analyst_gupta", "N. Gupta", "ANALYST", "Crime Analytics Unit"),
]


def _random_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    users = []
    print(f"{'username':<16}{'role':<14}{'password (SAVE THIS - shown once)'}")
    print("-" * 60)
    for username, full_name, role, rank_context in DEMO_USERS:
        password = _random_password()
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        users.append({
            "username": username,
            "full_name": full_name,
            "role": role,
            "rank_context": rank_context,
            "password_hash": password_hash,
        })
        print(f"{username:<16}{role:<14}{password}")

    OUT_PATH.write_text(json.dumps(users, indent=2))
    print(f"\nWrote {len(users)} demo users to {OUT_PATH} (hashes only)")
    print("Passwords above are shown ONCE and not saved anywhere - rerun this script to reset them.")


if __name__ == "__main__":
    main()
