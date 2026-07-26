# Project Status — Crime Intelligence Platform

Audit date: 2026-07-26. This is a snapshot, not a living spec — re-verify
against the actual code/console before trusting anything here after a
significant gap in time. Written after reading every doc in `docs/`, every
service's `README.md`, the current repo tree, git history, and the live
Zoho Catalyst console state.

## 1. What this is

A 10-service FastAPI backend implementing a scoped-down, honestly-reduced
version of the vision in
[`docs/architecture/Conversational Crime Analytics AI Research.md`](architecture/Conversational%20Crime%20Analytics%20AI%20Research.md)
("System Architecture for a Natural Language Conversational Crime
Intelligence and Multi-Tier Computational Criminology Platform"). That
research doc describes 8 conceptual sections built around LLMs, LangGraph,
Whisper ASR, Kannada TTS, Graph Attention Networks, and multi-agent OSINT
scraping. None of the LLM/agent infrastructure is available in this build
environment (no LLM API key, no audio pipeline) — so every pillar below is
a **real, working, deterministic substitute** for its corresponding
research-doc section, with the gap explicitly documented in that service's
own README rather than papered over. This pattern is consistent across all
10 services and is the single most important thing to understand about how
this codebase was built.

The platform is organized as **10 independently deployable FastAPI
microservices** ("pillars"), each with its own `requirements.txt`,
`.venv`, `app/config.py`, `app/rbac.py` (a literal copy per service, not a
shared import — each service is meant to be deployed/versioned
independently), `routers/`, and `tests/`.

## 2. Pillar-by-pillar status

| # | Pillar | Service dir | Port | Data | Tests | Deployed? |
|---|---|---|---|---|---|---|
| 1 | Conversational interface | `conversational-interface` | 8022 | seed (district names only) | 12 | live, needs 7 downstream URLs redeployed |
| 2 | Criminal network & relationship analysis | `network-analysis` | 8010 | synthetic seed | 13 | **live** |
| 3 | Crime pattern & trend analytics | `pattern-analytics` | 8011 | synthetic seed | 13 | **live** |
| 4 | Sociological crime insights | `sociological-insights` | 8012 | real 2011 Census + NCRB-calibrated | 14 | **live** |
| 5 | Offender profiling (recidivism) | `offender-profiling` | 8016 | synthetic seed, trained classifier | 16 | **live** |
| 6 | Investigator decision support | `investigator-decision-support` | 8018 | synthesis of pillars 2/3/4/5/8 | 13 | **live** |
| 7 | Financial crime / AML | `financial-crime-analysis` | 8013 | real IBM AML benchmark (5.08M txns) | 13 | **live** |
| 8 | Crime forecasting | `crime-forecasting` | 8014 | real NCRB district-wise IPC data | 10 | **live** |
| 9 | Explainable AI (SHAP) | `explainable-ai` | 8021 | derived from pillar 5's model | 9 | **live** |
| 10 | Auth / RBAC / governance | `auth-service` | 8020 | demo users (bcrypt-hashed) | 9 | **live** |

**122 tests total**, all passing as of the last full run. **All 10
services are live on Zoho Catalyst AppSail**, verified via `/health`
returning real loaded-record counts (not just a bare 200) for each one —
see the deployed URLs in `frontend/web-app/.env.local`. The one
outstanding step: `conversational-interface`'s 7 downstream `*_URL` env
vars were updated from `REPLACE_ME_...` placeholders to the real deployed
URLs (both in its `app-config.json` and, more importantly, in the actual
Catalyst Console — Console-deployed services ignore the zip's
`app-config.json`), but it needs a **redeploy** for that change to take
effect; not yet confirmed done as of this writing.

### What each pillar actually does

- **conversational-interface** (1): one `POST /api/chat/message` endpoint
  that classifies a short English query via ordered regex/keyword rules
  (`app/nlu.py` — not an LLM) into one of 10 intents, resolves
  pronoun/back-references via a per-session in-memory context dict (the
  LangGraph substitute), and forwards the caller's real bearer token
  unchanged to whichever of the other 7 services actually answers the
  question. The only service in this platform that makes live HTTP calls
  to its siblings rather than reading their precomputed files — a
  deliberate, documented exception.
- **network-analysis** (2): co-accused graphs, organized-group/community
  detection, key-actor ranking, shortest-path between suspects,
  repeat-offender lookups. In-memory graph loaded once from CSV at
  startup — no real graph database, no GAT-based link prediction (the
  research doc's vision) — flagged in its own README as a real limitation
  before this could handle a live, growing case database.
- **pattern-analytics** (3): DBSCAN geospatial hotspot clustering, PCA +
  K-Means district severity tiering, temporal trend/emerging-spike
  detection, MO-similarity matching. Directly follows the research doc's
  "Geospatial-Temporal Crime Pattern Analytics" section.
- **sociological-insights** (4): joins real 2011 Census district
  socioeconomic data with NCRB-calibrated district crime rates. One of two
  services in the platform not running on purely synthetic data.
- **offender-profiling** (5): trained classifier replacing the seed
  dataset's rule-based `risk_tier` placeholder, evaluated against that
  rule as a baseline on a held-out test set. `scikit-learn==1.7.1` is
  pinned exactly because `model.pkl` was trained with it — unpickling
  across sklearn versions is unreliable.
- **investigator-decision-support** (6): not a new analytics engine — a
  synthesis/dossier layer reading the *precomputed output files* of
  pillars 2, 3 (lightly reimplemented), 4, 5, and 8.
- **financial-crime-analysis** (7): the only service other than
  sociological-insights running on **fully real, non-synthetic** data —
  the IBM AML benchmark (5,078,345 transactions, 515,080 accounts, 5,177
  labeled laundering transactions). No LangGraph AML state machine, no
  live sanctions-list/PEP screening, no crypto tracing — those are the
  research doc's vision, not built here.
- **crime-forecasting** (8): Poisson/random-forest-style forecasting
  backtested against real held-out years of NCRB data. No OSINT
  multi-agent web intelligence layer (the research doc's other half of
  this section) — not built.
- **explainable-ai** (9): SHAP explanations for pillar 5's model. Six of
  the other seven analytics services are "transparent by construction"
  already (deterministic rules, not black-box models), so this service's
  real job is narrower than "explain everything" — see its own README for
  the reasoning.
- **auth-service** (10): JWT login, three roles
  (`ANALYST < INVESTIGATOR < ADMIN`), in-memory audit log. The platform's
  only `POST` endpoint besides conversational-interface's chat message
  (credentials can't go in a URL/query string). `JWT_SECRET` has an
  insecure hardcoded dev default with a loud startup warning — every other
  service verifies tokens statelessly using the *same* secret, so this is
  the one shared piece of config across the whole platform.

## 3. Cross-cutting architecture patterns

- **RBAC**: `ANALYST(1) < INVESTIGATOR(2) < ADMIN(3)`, stateless JWT
  verification (no callback to auth-service per request), identical
  `app/rbac.py` hand-copied into all 10 services rather than shared as a
  package — each service is meant to be deployed/versioned independently.
- **File-reading over live HTTP, except one deliberate exception**:
  investigator-decision-support and explainable-ai read other services'
  *precomputed output files* directly rather than calling them over HTTP —
  traded for demo reliability and graceful degradation. conversational-
  interface is the sole exception (see above), because it has to field
  unpredictable queries across all 7 analytics domains.
- **GET-only convention, with two deliberate exceptions**: every analytics
  endpoint is GET. `auth-service`'s login and `conversational-interface`'s
  chat message are the only `POST`s, for different reasons (credentials
  vs. free-text body) — both documented as deliberate, not oversights.
- **Honest scope reduction, repeated 10 times**: every service's README
  has an explicit "what the research doc wanted vs. what's actually built
  here, and why" section. This is the load-bearing convention of the
  entire codebase — worth preserving in any future pillar.

## 4. What's in the research doc but genuinely not built anywhere

Checked against all 10 services — these are real gaps, not oversights,
and each is a large undertaking on its own:

- **Judicial/legal NLP** (OpenNyAI: legal NER, rhetorical-role
  classification, BERTSUM summarization of FIRs/judgments) — no
  corresponding pillar exists at all. This is the one research-doc section
  with zero service behind it.
- **LLM-based NLU, LangGraph dialogue state, Whisper ASR, Kannada TTS/G2P,
  signed-PDF session export** — conversational-interface substitutes
  regex/keyword matching + a plain context dict; no audio pipeline exists
  anywhere in this repo.
- **Graph Attention Networks for link prediction** (network-analysis,
  financial-crime-analysis) — both use simpler graph algorithms, not GNNs.
- **LangGraph AML state machine, live sanctions/PEP list screening, crypto
  wallet tracing** — financial-crime-analysis does none of these; it's
  feature-engineering + a trained classifier on the IBM benchmark.
- **Multi-agent OSINT web intelligence** (CrewAI/Perplexity-based
  darknet/forum scraping) — not built; crime-forecasting only does the
  statistical-forecasting half of that research-doc section.
- **FairLens-style formal bias/fairness auditing pipeline** — not built as
  a standalone pipeline. Some mitigation exists implicitly (offender-
  profiling's feature set doesn't include protected attributes like
  religion/caste), but there's no dedicated statistical-parity auditor.
- **Cryptographically sealed/tamper-evident audit log, DPDPA-specific
  compliance tooling** — auth-service's audit log is a plain in-memory
  Python list, explicitly documented as a demo-scope limitation, not
  cryptographically sealed.

## 5. Repo structure: real vs. scaffolding

Confirmed via file counts, not assumptions:

| Path | Status |
|---|---|
| `backend/services/*` | **Real** — all 10 services, full implementations |
| `data/`, `scripts/data_generation/*` | **Real** — seed/processed data generation pipelines |
| `docs/architecture/` | **Real** — 2 research/planning docs + 1 confidential PDF (gitignored) |
| `docs/deployment/` | **Real** — `DEPLOY.md`, written and validated against a live deploy |
| `database/migrations/*.sql` | Real files (2), but **unused** — no service connects to a relational DB |
| `data/processed/fir_system_oltp.sqlite` | Exists (3.8 MB) but **unused** — no service imports `sqlite3` |
| `frontend/web-app/` | **Real** — React 19 + TypeScript + Vite, all 11 pages/API clients/auth store built, builds clean (`npm run build`). Corrects this doc's earlier claim, which was based on an incomplete (`-maxdepth 2`) directory scan. Not yet deployed anywhere. |
| `infra/{docker,kubernetes,terraform}` | **Empty scaffold** (0 files) |
| `ml-pipeline/`, `nlp-models/` | **Empty scaffold** (0 files) — superseded by the actual per-service `scripts/data_generation/<pillar>/` pattern |
| top-level `tests/{e2e,integration,unit}` | **Empty scaffold** (0 files) — no cross-service integration tests exist; only per-service unit tests and manual smoke tests |
| `docs/api/`, `docs/compliance/` | **Empty scaffold** (0 files) |

The empty directories all look like leftovers from an initial
project-structure plan that predates the actual microservices build-out.
Worth a decision: delete them, or treat them as a real backlog
(frontend and integration tests being the two that would matter most).

## 6. Deployment status (Zoho Catalyst AppSail)

Full detail in [`docs/deployment/DEPLOY.md`](deployment/DEPLOY.md) — this
is the condensed version.

**All 10 services are live**, each verified individually via `/health`
returning real loaded-record counts, not just a bare 200 (e.g.
financial-crime-analysis: 515,080 accounts loaded; pattern-analytics:
5,000 FIRs loaded). Deployed URLs are in
`frontend/web-app/.env.local` (gitignored - not in this doc to avoid two
sources of truth going stale independently).

Getting the first service (`auth-service`) live surfaced three real bugs,
all fixed and applied to all 10 services before the rest were deployed:

1. **Catalyst's Managed Runtime does not run `pip install`.** Every
   service's dependencies must be pre-installed ("vendored") into a
   `vendor/` folder before upload. Because Catalyst's runtime is Linux
   (`/var/lang/bin/python3`) and this repo is developed on Windows,
   `scripts/deploy/vendor_service_deps.py` cross-downloads Linux x86_64
   wheels explicitly (`--platform manylinux2014_x86_64
   --python-version 313 ...`) rather than relying on the host OS's own
   pip resolution.
2. **The startup command isn't run through a shell.** A command containing
   `$X_ZOHO_CATALYST_LISTEN_PORT` was passed through literally, not
   interpolated — fixed by wrapping every service's startup command in
   `sh -c '...'`.
3. **`app/config.py`'s repo-root path computation crashed at import time
   in the deployed (flat) directory structure** — `_SERVICE_DIR.parents[2]`
   assumed the local monorepo's on-disk depth, which doesn't exist once a
   zip is unpacked flat inside the container. Fixed with a depth check
   that falls back gracefully; a no-op change for local dev. Applied to
   all 10 `app/config.py` files, verified against each service's test
   suite (all still pass).

Also discovered: `catalyst init`'s and `catalyst appsail:add`'s AppSail
setup crash with `TypeError: appsailConfig.map is not a function`
(CLI `1.27.0`, currently npm's latest) — reproduced identically with zero
or one AppSail already registered, so it's a CLI bug, not something fixable
from this repo. **Console-based deploys work and are the proven path** —
`catalyst deploy appsail` (redeploy of an *already-registered* service,
not creating a new one) hasn't been tried yet and might still work via CLI.

A **Console-deployed service ignores `app-config.json` inside the zip
entirely** — its startup command, port, memory, and env vars are stored as
settings on the service itself (Console → Configuration tab), not read
from the uploaded archive. `app-config.json` is kept in the repo as the
source of truth for what those Console settings *should* be, and matters
for real if the CLI path ever starts working.

### What's left to actually finish the deployment

1. ~~Upload the remaining 9 zips~~ — done, all 10 confirmed live via
   `/health`.
2. ~~Set `JWT_SECRET` + `JWT_ALGORITHM` on all 10 services~~ — done.
3. **`conversational-interface`'s 7 downstream `*_URL` env vars were
   updated** (in both its `app-config.json` and, more importantly, the
   actual Catalyst Console) **but the redeploy to apply them hasn't been
   confirmed yet.** Until that redeploy happens, every chat intent except
   `help` will still fail with "isn't reachable right now."
4. Re-run the verification curl sequence in `DEPLOY.md` step 7 end-to-end
   (login → call an ANALYST endpoint → confirm a 403 on an
   INVESTIGATOR-gated one) — done for auth-service's own login; not yet
   done as a full chat-message round trip through conversational-interface
   to a downstream service.
5. Demo credentials are now fixed (not random) — see
   `scripts/data_generation/auth/build_demo_users.py`; the six accounts and
   passwords are documented there and in this session's chat history, not
   duplicated here to avoid a third copy going stale.
6. Frontend (`frontend/web-app/`) is fully built (all pages, API clients,
   auth store — contrary to this doc's earlier claim that it was empty
   scaffolding; that was based on an incomplete directory scan) and builds
   cleanly with `npm run build`. Not yet deployed anywhere — currently only
   runnable via `npm run dev` locally against the live backend.

## 7. Git / version control state

Current branch `main`, in sync with `origin/main` (0 ahead / 0 behind).
Recent commits (all authored by the repo owner directly, not by this
assistant — per this session's standing rule, nothing gets committed or
pushed without explicit per-turn permission, and none was requested):

```
d5c9b30 feat: Update app-config and config files for service dependency
        management and environment variable adjustments
7595175 chore: Replace app-config.json.mine with app-config.json for auth-service
9200d05 feat: Implement conversational interface service with JWT
        authentication and role-based access control
```

Worth a decision, not acted on here: `scripts/deploy/*.zip` are tracked in
git (`auth-service-deploy.zip` already committed; the other 9 are
currently untracked). These are regenerable build artifacts (same category
as `vendor/` and `data/`, which *are* gitignored) — committing multi-tens-
of-MB binaries to git history is generally worth avoiding. Flagging this
rather than changing `.gitignore` unilaterally, since the auth-service zip
is already committed and reversing that is a judgment call for whoever
owns the repo.

## 8. Known limitations / risks (not fixed by this audit)

- **In-memory state resets on every restart/redeploy**: auth-service's
  audit log, conversational-interface's chat sessions, network-analysis's
  in-memory graph. Documented per-service as demo-scope, not oversights.
- **`JWT_SECRET` insecure dev default**: every service falls back to a
  hardcoded, publicly-visible-in-this-repo secret if the env var isn't
  set, with a loud startup warning. Must be set to a real random value
  before any real deployment — already done for auth-service on Catalyst;
  needs doing for the other 9 as they deploy.
- **No refresh-token flow**: 60-minute access tokens, forced re-login.
- **Billing**: AppSail bills by instance uptime. Running all 10 services
  continuously has a real ongoing cost — Catalyst's specific AppSail
  free-tier allowance couldn't be confirmed from public docs; worth
  checking the console's billing page directly before leaving all 10
  running.
- **No CI/CD**: every deploy so far is a manual Console upload. Nothing
  auto-deploys on push.
- **No cross-service integration tests**: the only proof all 10 services
  work together is the manual smoke tests run by hand during this build.
  `tests/` at the repo root (e2e/integration) is empty scaffolding.
- **Frontend deployed via Zoho Catalyst Slate**:
  https://crime-intel-frontend-cgujvxbi.onslate.in — `catalyst slate:link
  --source ./frontend/web-app` then `catalyst deploy slate
  crime-intel-frontend` from the repo root. Hit one real bug on the way:
  `package.json` had `@rolldown/binding-win32-x64-msvc` pinned as a plain
  `devDependency` (should resolve per-platform automatically, like esbuild
  does) - broke the build on Slate's Linux runner with `EBADPLATFORM`.
  Removed it, regenerated `package-lock.json`, confirmed the Windows build
  still worked locally, then redeployed successfully. Also worth knowing:
  `catalyst deploy slate` packages your **local working directory**
  directly (including gitignored `.env.local`), not a git clone - unlike
  a separate GitHub-integration-based Slate deploy attempted first in the
  console, which cloned from `origin/main` and silently skipped
  install/build/output because no build config was set there. That
  GitHub-integration Slate app is still sitting in the console, broken and
  unused - worth deleting to avoid confusion between the two.
- **`explainable-ai`'s deploy zip was ~140 MB** (shap + scipy +
  scikit-learn + numba/llvmlite, all vendored as Linux wheels) and
  uploaded successfully — no longer a real risk, but the largest zip by
  far if it ever needs rebuilding.

## 9. Suggested next steps (not started, for the user to prioritize)

In roughly the order they'd naturally come up:

1. Confirm `conversational-interface`'s redeploy actually picked up the 7
   real downstream URLs — test a real chat message end-to-end, not just
   `/health`.
2. ~~Deploy the frontend~~ — done:
   https://crime-intel-frontend-cgujvxbi.onslate.in (unlike AppSail,
   Slate's CLI link/deploy commands worked without hitting the
   `appsailConfig.map` bug). Delete the unused, broken GitHub-integration
   Slate app left over from the first attempt (see §6).
3. Decide the fate of the empty scaffold directories (§5) — delete, or
   turn into real backlog items.
4. Decide whether `scripts/deploy/*.zip` belong in git history (§7).
5. If sharing this publicly or handing it to others, replace every
   service's dev-default `JWT_SECRET` posture with something that refuses
   to boot on an insecure default in a "production" env, rather than just
   warning.
