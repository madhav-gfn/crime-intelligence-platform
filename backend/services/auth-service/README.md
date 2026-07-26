# auth-service

Secure RBAC / governance (pillar 10). JWT-based login, three roles, and an
audit log — the platform's first service with any access control at all.
Before this, every one of the seven analytics services had `allow_origins=["*"]`
and zero verification on any endpoint, which is a real gap for a platform
that (even in demo form) serves individual-level predictive risk scores
and case data. All seven now enforce it (see the table below).

## Roles

| Role | Access |
|---|---|
| `ANALYST` | Aggregate/statistical endpoints only |
| `INVESTIGATOR` | Adds anything naming a specific person, case, or account (PII-adjacent) |
| `ADMIN` | Everything, including the audit log |

Roles are ranked (`ANALYST` < `INVESTIGATOR` < `ADMIN`), so a higher role
always satisfies a lower requirement — an `ADMIN` token works anywhere an
`INVESTIGATOR` token would.

## How token verification works across services

Every service in this platform is deployed and versioned independently
(own `requirements.txt`, own venv — see the Zoho Catalyst AppSail
deployment notes in `docs/architecture/`). Rather than have every request
to, say, `offender-profiling` call back to `auth-service` to check a
token, each protected service verifies JWTs **statelessly**: it holds the
same `JWT_SECRET`/`JWT_ALGORITHM` and decodes the token itself. That's the
standard JWT microservices pattern, and it's what actually keeps
`auth-service` and every downstream service in sync — not shared code.

Every service has its own `app/rbac.py` — a literal copy, not a shared
import (each service is deployed/versioned independently with its own
`requirements.txt`; see any `rbac.py`'s docstring for the same rationale
`taxonomy.py`/`crime_type_profiles.py` already established elsewhere in
this repo). What's shared is the `JWT_SECRET`/`JWT_ALGORITHM` env vars,
not code.

Endpoints that name a specific person, account, or entity require
`INVESTIGATOR`; endpoints that only ever return district/case-level
aggregates stay at `ANALYST`. Per service:

| Service | `INVESTIGATOR`-gated | `ANALYST`-only |
|---|---|---|
| `network-analysis` | `/graph`, `/person/{id}`, `/person/{id}/ego`, `/communities`, `/hubs`, `/path`, `/repeat-offenders` (all surface names) | `/stats` |
| `offender-profiling` | `/person/{id}`, `/risk-list`, `/predict` | `/model-info` |
| `financial-crime-analysis` | `/account/{id}`, `/suspicious-accounts`, `/patterns`, `/path` | `/stats`, `/evaluate` |
| `investigator-decision-support` | `/person-dossier/{id}` | everything else |
| `pattern-analytics` | none — no person-identifying output | all endpoints |
| `sociological-insights` | none — district-level only | all endpoints |
| `crime-forecasting` | none — district-level only | all endpoints |
| `explainable-ai` | `/person/{id}` (real person's SHAP explanation) | `/methodology`, `/model-info`, `/predict-explain` (hypothetical profile) |
| `conversational-interface` | none directly - `/api/chat/message` forwards the caller's own token to whichever downstream service answers the query, and that service's own gate applies | `/message`, `/capabilities`, `/session/{id}/history` (all `ANALYST` floor) |

This was built incrementally: `offender-profiling` first, as a concrete
end-to-end proof (real login, real token, real 401/403s verified against
two live running services), then the same mechanical pattern applied to
the remaining six — each retrofit came with its own new tests (401 with
no token, 403 for an under-privileged role, 200 for the right one), not
just code copied and assumed to work.

## Demo users

Regenerate locally to get your own random demo credentials (passwords are
printed once, never written to disk in plaintext, and never committed —
`data/processed/` is gitignored repo-wide):

```bash
python scripts/data_generation/auth/build_demo_users.py
```

Six users are seeded: `admin` / `sp_reddy` (ADMIN), `pi_sharma` / `si_verma`
(INVESTIGATOR), `analyst_iyer` / `analyst_gupta` (ANALYST) — flavored with
real Indian police rank context (Superintendent, Inspector, Sub-Inspector)
as `rank_context`, though only `role` is ever used for access control.

## Audit log

`GET /api/auth/audit-log` (ADMIN-only) returns recent login attempts
(success and failure) and access-denied events from other services'
`require_role` checks that choose to log them. **In-memory, resets on
service restart** — a documented limitation, not an oversight. Real
governance requirements typically want tamper-evident, durable audit
storage (an append-only log store, not a Python list); this demonstrates
the shape of what gets recorded and who can read it without pretending to
solve durable storage in a demo build.

## Security notes (read before deploying this anywhere real)

- `JWT_SECRET` defaults to an **insecure, hardcoded dev value**. The
  service logs a loud warning at startup if it's still in use. Set a real
  `JWT_SECRET` env var (32+ random bytes) before any deployment, and make
  sure every service that verifies tokens is configured with the exact
  same value.
- Passwords are hashed with bcrypt (`bcrypt.hashpw`/`checkpw`) — never
  stored or logged in plaintext.
- Login is the one `POST` endpoint in this entire platform — every other
  service is GET-only. Credentials must never travel in a URL/query
  string (they'd land in server/proxy access logs), so this is a
  deliberate, necessary exception to the platform's GET-only convention.
- Access tokens expire after 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  There is no refresh-token flow in this build — a real deployment would
  want one rather than 60-minute forced re-logins.

## Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/auth/login` | `{username, password}` → JWT access token + role. |
| `GET /api/auth/me` | Identity of the caller's token. |
| `GET /api/auth/audit-log?limit=` | ADMIN-only: recent login/access-denied events. |

## Setup

```bash
pip install -r requirements.txt
python scripts/data_generation/auth/build_demo_users.py   # writes data/processed/auth/users.json
python -m uvicorn app.main:app --reload --port 8020
```

## Tests

```bash
python -m pytest tests/ -v
```

## Deployment

See [docs/deployment/DEPLOY.md](../../../docs/deployment/DEPLOY.md) for the
Zoho Catalyst AppSail deploy guide (backend-only, no frontend yet). This
service's `JWT_SECRET` must be set to the same value across all 10 services
- see this README's "How token verification works across services" above.
