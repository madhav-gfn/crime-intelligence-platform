# Deploying the backend to Zoho Catalyst AppSail

Deploys the 10 backend microservices only - there is still no frontend
(`frontend/web-app/` is empty scaffolding). Every service stays reachable
as a plain REST API (Swagger UI at `/docs`) until a UI exists.

This is a hand-written deployment config, not something run or verified
against a real Zoho account in this environment (that requires an
interactive OAuth login the CLI can't do headlessly). Treat the files below
as a strong starting point; the `catalyst` CLI's own interactive wizard is
authoritative if anything here doesn't match what it expects.

## What's been prepared

- `catalyst.json` (repo root) - lists all 10 services as AppSail targets.
- `backend/services/<name>/app-config.json` - one per service: start
  command, Python stack, memory, and env var overrides for that service's
  data paths.
- `scripts/deploy/stage_service_data.py` - copies each service's required
  slice of `data/seed` / `data/processed/*` into `backend/services/<name>/data/`
  so the service is self-contained for upload. AppSail only packages files
  inside a target's own directory, and every service already resolves its
  data paths via individually overridable env vars (see each `app/config.py`)
  - the `*_PATH`/`*_DIR` values in `app-config.json` point at these staged
    copies instead of the shared repo-root `data/`. No application code
  changed.

No secrets are in any of these files. `JWT_SECRET` is deliberately left out
of every `app-config.json` - set it via the Catalyst Console after the
service exists (see step 4).

## 0. Prerequisites

- A Zoho Catalyst account and a Catalyst project created in the console.
- `npm install -g zcatalyst-cli`, then `catalyst login`.
- All 10 services' data generated locally first - run whatever
  `scripts/data_generation/**` pipelines you'd normally run for local dev
  (see each service's README), including
  `python scripts/data_generation/auth/build_demo_users.py` for auth-service.
  `data/seed/` and `data/processed/**` must be populated before staging.

## 1. Stage each service's data

```bash
python scripts/deploy/stage_service_data.py all
```

Re-run this (for the affected service, or `all`) any time the source data
changes and before every redeploy - it deletes and rebuilds each service's
`data/` folder from scratch.

## 2. Initialize the Catalyst project

From the repo root:

```bash
catalyst init
```

Pick your portal and project. When it asks about AppSail, register the
first service (e.g. `backend/services/auth-service`) as a
**Catalyst-Managed Runtime**, Python stack. This generates `.catalystrc`
(gitignored - machine-specific) and may rewrite `catalyst.json`; reconcile
it with the 10-target version already in the repo if the wizard overwrites
it. For the remaining 9 services, register each with:

```bash
catalyst appsail:add
```

...pointing at each `backend/services/<name>` directory in turn.

## 3. Deploy order

Deploy in this order, because `conversational-interface` needs the other
7 services' live URLs and every service needs the same `JWT_SECRET`:

1. `auth-service`
2. The 7 analytics services (any order): `network-analysis`,
   `pattern-analytics`, `sociological-insights`, `financial-crime-analysis`,
   `crime-forecasting`, `offender-profiling`, `investigator-decision-support`,
   `explainable-ai`
3. `conversational-interface` last

```bash
catalyst deploy appsail
```

(run per target, or select the target when prompted). Note the live URL
Catalyst prints for each service.

## 4. Set environment variables via the Catalyst Console

For **every** one of the 10 services (Console -> AppSail -> service ->
Environment Variables):

- `JWT_SECRET` - one real random value, **identical across all 10 services**
  (that shared secret is how every service verifies auth-service's tokens
  statelessly - see `backend/services/auth-service/README.md`). Generate
  one with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `JWT_ALGORITHM=HS256` (matches the default, but set it explicitly).

For `conversational-interface` only, also replace the 7
`REPLACE_ME_after_deploying_*` placeholders in its env vars with the real
URLs noted in step 3:
`NETWORK_ANALYSIS_URL`, `PATTERN_ANALYTICS_URL`,
`FINANCIAL_CRIME_ANALYSIS_URL`, `CRIME_FORECASTING_URL`,
`OFFENDER_PROFILING_URL`, `INVESTIGATOR_DECISION_SUPPORT_URL`,
`EXPLAINABLE_AI_URL`.

Redeploy each service after changing its env vars.

## 5. Verify

```bash
curl https://<auth-service-url>/health
curl -X POST https://<auth-service-url>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "analyst_iyer", "password": "<from build_demo_users.py output>"}'
# then hit an ANALYST-gated endpoint on another service with the returned token,
# and confirm a 403 on an INVESTIGATOR-gated one with the same ANALYST token.
```

## Known limitations of this deployment (not fixed by this guide)

- **In-memory state resets on every restart/redeploy**: auth-service's
  audit log and conversational-interface's chat sessions are plain
  in-process state - already documented in both services' READMEs as a
  demo-scope limitation, not something specific to Catalyst.
- **AppSail's ~10-second cold-start port-bind window**: a few services
  load pandas/sklearn/shap at startup (see each `lifespan()`). If a cold
  start times out, the fix is deferring heavy loads until after the port
  binds (see the pattern in this repo's Zoho Catalyst research doc) -
  worth checking during initial deploy, not pre-emptively built here since
  it may not be needed.
- **Billing**: AppSail bills by instance uptime, not per-request. Running
  10 always-on services has a real ongoing cost - check current Catalyst
  pricing/free-tier limits before deploying all 10, rather than assuming
  this guide's scope is free.
- **No CI/CD**: this is a manual `catalyst deploy appsail` per service.
  Nothing here wires up auto-deploy on push.
