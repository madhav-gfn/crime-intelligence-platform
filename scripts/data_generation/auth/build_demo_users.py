"""
Generates the demo user store for auth-service (pillar 10). Only bcrypt
password hashes are ever written to disk - the plaintext passwords below
are fixed, not randomly generated, so they stay stable across reruns and
redeploys instead of invalidating themselves every time this script runs.
This is the same "insecure by design, loud warning, change before any real
deployment" posture as JWT_SECRET's dev default (see
backend/services/auth-service/app/config.py) - these are demo credentials
for a platform with no real users yet, not something masquerading as
production-grade secret management.

Roles (see backend/services/auth-service/README.md for the full RBAC
rationale):
    ANALYST      - aggregate/statistical endpoints only
    INVESTIGATOR - adds person/case/account-level (PII-adjacent) access
    ADMIN        - full access, including the audit log

Usage:
    python scripts/data_generation/auth/build_demo_users.py
"""
import json
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = ROOT / "data" / "processed" / "auth" / "users.json"

# (username, full_name, role, rank_context, password) - rank_context is
# flavor text only, not used for access control (role is the only thing
# that matters). Passwords are fixed demo values, not secrets - see the
# module docstring.
DEMO_USERS = [
    ("admin", "Admin User", "ADMIN", "System Administrator", "Admin@Demo123"),
    ("sp_reddy", "K. Reddy", "ADMIN", "Superintendent of Police", "Reddy@Demo123"),
    ("pi_sharma", "R. Sharma", "INVESTIGATOR", "Police Inspector", "Sharma@Demo123"),
    ("si_verma", "A. Verma", "INVESTIGATOR", "Sub-Inspector", "Verma@Demo123"),
    ("analyst_iyer", "S. Iyer", "ANALYST", "Crime Analytics Unit", "Iyer@Demo123"),
    ("analyst_gupta", "N. Gupta", "ANALYST", "Crime Analytics Unit", "Gupta@Demo123"),
]


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    users = []
    print(f"{'username':<16}{'role':<14}{'password'}")
    print("-" * 60)
    for username, full_name, role, rank_context, password in DEMO_USERS:
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
    print("These are fixed demo credentials, not secrets - see the module docstring.")


if __name__ == "__main__":
    main()
