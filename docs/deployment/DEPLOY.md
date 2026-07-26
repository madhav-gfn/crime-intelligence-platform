# Deploying the backend to Zoho Catalyst AppSail

Deploys the 10 backend microservices only - there is still no frontend
(`frontend/web-app/` is empty scaffolding). Every service stays reachable
as a plain REST API (Swagger UI at `/docs`) until a UI exists.

This guide reflects a real deploy of `auth-service` that's live and passing
`/health` - not just a plan. Getting there surfaced three real bugs, all
fixed below (two in this repo, one worked around). Follow this path for the
remaining 9 rather than the CLI-init flow this guide originally described.

## What's been prepared

- `backend/services/<name>/app-config.json` - start command, Python stack,
  memory, and env var overrides for that service's data paths. **Only
  relevant if you deploy via the CLI** (`catalyst deploy appsail`) - a
  Console-created service ignores this file entirely and stores its own
  startup command / port / env vars as settings on the service itself (see
  step 3). Kept in the repo anyway as the source of truth for what those
  Console settings should be.
- `scripts/deploy/stage_service_data.py` - copies each service's required
  slice of `data/seed` / `data/processed/*` into `backend/services/<name>/data/`.
  Every service already resolves its data paths via individually
  overridable env vars (see each `app/config.py`).
- `scripts/deploy/vendor_service_deps.py` - installs each service's
  `requirements.txt` into `backend/services/<name>/vendor/`, targeting
  **Linux x86_64 CPython wheels** regardless of your host OS. Required -
  see step 3.
- `scripts/deploy/build_deploy_zip.py` - zips `app/`, `data/`, `vendor/`,
  `app-config.json`, and `requirements.txt` for one service with those
  directly at the zip root (no nested `<name>/` folder), ready for Console
  upload.

`catalyst.json` (repo root) still lists all 10 services as AppSail targets
for whenever the CLI's `init`/`appsail:add` flow works (see step 2) - it's
unused by the Console path.

No secrets are in any deploy file. `JWT_SECRET` is set via the Catalyst
Console per service (step 4), never committed.

## 0. Prerequisites

- A Zoho Catalyst account and a Catalyst project created in the console
  (first project must be created from the console, not the CLI).
- `npm install -g zcatalyst-cli`, then `catalyst login` - only needed if you
  want to try the CLI path (step 2); the Console path (step 3) doesn't need
  either.
- All 10 services' data generated locally first - run whatever
  `scripts/data_generation/**` pipelines you'd normally run for local dev
  (see each service's README), including
  `python scripts/data_generation/auth/build_demo_users.py` for auth-service.
  `data/seed/` and `data/processed/**` must be populated before staging.

## 1. Stage each service's data and vendor its dependencies

```bash
python scripts/deploy/stage_service_data.py all
python scripts/deploy/vendor_service_deps.py all
python scripts/deploy/build_deploy_zip.py all
```

Re-run all three (for the affected service, or `all`) any time source data,
`requirements.txt`, or app code changes, and before every redeploy - each
one deletes and rebuilds its output from scratch. `vendor_service_deps.py`
is the slow one (downloads real packages); `build_deploy_zip.py` needs both
the other two to have already run.

**Why vendoring is required at all**: Catalyst's Managed Runtime does not
run `pip install` for you - confirmed live (a first deploy without `vendor/`
crashed with `No module named uvicorn` even though `requirements.txt` lists
it) and by Catalyst's own Python AppSail docs, which say to manually install
packages into the build directory before upload. This is true whether you
deploy by ZIP or via the GitHub integration - neither runs a build step.

**Why cross-platform matters if you're on Windows/Mac**: Catalyst's runtime
is Linux (`/var/lang/bin/python3` in crash logs is the giveaway - AWS
Lambda's custom-runtime convention). A plain `pip install -r
requirements.txt -t .` on a non-Linux host would fetch host-platform
binaries for anything with a C extension (bcrypt, numpy, pandas,
scikit-learn, scipy, shap, uvloop, httptools...) that won't run in the
container. `vendor_service_deps.py` passes `--platform manylinux2014_x86_64`
(and a few newer manylinux tags) plus `--python-version 313 --implementation
cp --abi cp313` so pip cross-downloads the right wheels no matter what OS
you're running the script on. Verify it worked with:

```bash
find backend/services/<name>/vendor -iname "*.so" | head
```

You should see `*-linux-gnu.so` files, not `.pyd`.

## 2. Try the CLI first (may not work - see below)

```bash
catalyst init
```

Pick your portal and project, select **AppSail** only, **Catalyst-Managed
Runtime**, decline the example-AppSails prompt, say no to initializing in
the current directory, then give the absolute path to a service (e.g.
`backend/services/auth-service`). For the remaining services:

```bash
catalyst appsail:add
```

**Known issue**: as of CLI `1.27.0` (npm's current latest at the time of
writing), both `catalyst init`'s AppSail step and `catalyst appsail:add`
crashed for this project with:
```
TypeError: appsailConfig.map is not a function
  at zcatalyst-cli/lib/util_modules/config/lib/appsail.js:112
```
This reproduced identically whether the project had zero or one AppSail
services already registered - it's a bug in the CLI itself, not something
fixable from this repo. If you hit the same error, skip to step 3 (Console)
for every service; there's no evidence it depends on anything
project-specific, but it's worth a quick retry since a CLI update could fix
it silently.

## 3. Deploy via Console (proven path - use this if step 2 fails)

For each service, in the Catalyst console:

1. **Serverless -> AppSail -> Deploy from Console**.
2. Deployment Type: **Catalyst-Managed Runtime**. Runtime: **Python 3.13**
   (or the closest available - matches `vendor_service_deps.py`'s target).
3. Service name: the service directory name (e.g. `auth-service`).
4. **Startup Command** - not the value in `app-config.json` verbatim, see
   next section:
   ```
   sh -c 'python3 -m uvicorn app.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT'
   ```
5. Memory: `512` (or `1024` for `offender-profiling` and `explainable-ai`,
   which load a scikit-learn model / SHAP at startup - see their
   `app-config.json` for the exact value used).
6. Build directory: upload `scripts/deploy/<name>-deploy.zip` from step 1.
7. Environment Variables: `PYTHONPATH=./vendor`, plus that service's
   `*_PATH`/`*_DIR` overrides - copy the `env_variables` block from that
   service's `app-config.json`.

**Why `sh -c '...'` and not the plain command**: Catalyst does not run
the startup command through a shell - it executes it directly. A command
containing `$X_ZOHO_CATALYST_LISTEN_PORT` gets passed through *literally*,
and uvicorn fails with `Error: Invalid value for '--port':
'$X_ZOHO_CATALYST_LISTEN_PORT' is not a valid integer`. Wrapping in
`sh -c '...'` forces an actual shell to interpolate the env var first.

**Important**: for a Console-created service, `app-config.json` inside the
zip is **not read** - the startup command, port, memory, and env vars you
set in the wizard (or later under the **Configuration** tab) are what
actually run. Re-uploading a zip via **Create Deployment** only replaces
the code; it does not re-read `app-config.json`. If you change the command
or env vars, edit them directly under **Configuration**, not just in the
zip.

## 4. The `_REPO_ROOT` bug (already fixed in this repo - context only)

Every service's `app/config.py` computed a fallback repo-root path assuming
the local monorepo's on-disk depth
(`repo_root/backend/services/<name>/app/config.py`). A Console/CLI deploy
unpacks the zip flat (`/catalyst/app/...`, no `backend/services/<name>/`
nesting), so that computation raised `IndexError: 2` **at import time**,
before any env var override could matter - it crashed even though every
actual data path is overridden via env var in production. Fixed with a
depth check that falls back to the service dir itself when the container's
tree isn't as deep as local dev's:
```python
_REPO_ROOT = _SERVICE_DIR.parents[2] if len(_SERVICE_DIR.parents) >= 3 else _SERVICE_DIR
```
This is a no-op locally (the parents do go that deep there) - already
applied to all 10 `app/config.py` files, verified against each service's
test suite.

## 5. Deploy order

Deploy in this order, because `conversational-interface` needs the other
7 services' live URLs and every service needs the same `JWT_SECRET`:

1. `auth-service`
2. The 7 analytics services (any order): `network-analysis`,
   `pattern-analytics`, `sociological-insights`, `financial-crime-analysis`,
   `crime-forecasting`, `offender-profiling`, `investigator-decision-support`,
   `explainable-ai`
3. `conversational-interface` last

## 6. Set environment variables

For **every** one of the 10 services (Console -> AppSail -> service ->
Configuration -> Environment Variables):

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
URLs noted in step 5:
`NETWORK_ANALYSIS_URL`, `PATTERN_ANALYTICS_URL`,
`FINANCIAL_CRIME_ANALYSIS_URL`, `CRIME_FORECASTING_URL`,
`OFFENDER_PROFILING_URL`, `INVESTIGATOR_DECISION_SUPPORT_URL`,
`EXPLAINABLE_AI_URL`.

Redeploy each service after changing its env vars.

## 7. Verify

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
  load pandas/sklearn/shap at startup (see each `lifespan()`). Not an issue
  observed on auth-service's deploy; worth watching for the heavier
  services (`offender-profiling`, `explainable-ai`).
- **Zip size**: `explainable-ai`'s deploy zip is ~140 MB (shap + scipy +
  scikit-learn + numba/llvmlite, all vendored as Linux wheels). Worked in
  testing so far; if a future upload is rejected for size, that's the
  first thing to look at.
- **Billing**: AppSail bills by instance uptime, not per-request. Running
  10 always-on services has a real ongoing cost - check current Catalyst
  pricing/free-tier limits before deploying all 10, rather than assuming
  this guide's scope is free.
- **No CI/CD**: this is a manual per-service deploy. Nothing here wires up
  auto-deploy on push.
