# offender-profiling

Criminology-based offender profiling (pillar 5). Replaces the rule-based
`risk_tier` placeholder shipped in `data/seed/offender_profile.csv`
(`prior_case_count` thresholds only — `used_weapon_ever` is always `False`
under the real FIR schema, see `scripts/data_generation/oltp/README.md`)
with an actual trained classifier, evaluated on a held-out test set and
against that same rule as a baseline.

## The task, precisely

**"Does this person, having just appeared as ACCUSED in a case, appear as
ACCUSED again within the next 365 days?"** A fixed follow-up window (not
"do they ever reoffend") is the standard framing in criminology recidivism
research (1-year re-arrest rate is a common metric), and it solves a real
data problem rather than ignoring it: cases near the end of the 2020-2024
observation window haven't had time to show reoffense yet, even if it
would happen in reality. Case appearances without a full 365-day follow-up
window remaining in the data are **excluded from training and evaluation**
(right-censored), not silently labeled "no reoffense." On the current
build: 8,675 total accused case-appearances, 6,979 eligible (1,696
censored), 24.0% positive rate among eligible appearances.

## Leakage discipline

- Every feature uses only a person's case history strictly **before** the
  case being scored - nothing from later cases.
- **No network-graph features** (co-accused degree, community membership)
  even though `network-analysis` computes them - that graph is built from
  the *entire* dataset and would leak future co-accusal relationships into
  a feature meant to represent "prior" knowledge. Left out on purpose.
- Train/test split is **by person**, not by case-appearance - a person's
  multiple appearances never land on both sides of the split.
- `occupation` / `income_bracket` are excluded: `person.csv` only
  populates them for `COMPLAINANT`-role rows (a real-schema gap, see the
  OLTP README) - confirmed 100% missing for every ACCUSED person before
  deciding to drop rather than impute them.

## Model comparison (on the real held-out test set)

| Model | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| Logistic Regression | 35.1% | 52.5% | 42.1% | 0.633 |
| **Random Forest (selected)** | 37.9% | 55.9% | 45.2% | **0.651** |
| Baseline (prior_case_count >= 1) | 34.8% | 57.8% | 43.5% | n/a (binary rule) |

Modest, honestly reported: the trained model edges out the old rule on
precision and F1, but the margin is real, not dramatic - ROC-AUC of 0.65
is "somewhat better than a coin flip," not a solved problem. That's
consistent with recidivism prediction generally being a hard, noisy task,
and with this specific dataset only offering ~7k labeled examples and no
features about the offense's severity of outcome, victim relationship, or
socioeconomic context (deliberately excluded, or absent from the real
schema - see above). Selected model is chosen by backtested ROC-AUC, not
by whichever number looks best.

## Risk tiers are percentile-based, not fixed thresholds

The model's predicted probabilities cluster tightly (~0.29-0.81 in the
current build, median ~0.44) - fixed bins like 0-0.33/0.33-0.66/0.66-1.0
would dump nearly everyone into one tier. Tiers are instead derived from
the actual score distribution: **HIGH** = top 10% (>= P90), **MEDIUM** =
next 25% (P65-P90), **LOW** = the rest - same rationale as the P99
fan-out/fan-in thresholds in `financial-crime-analysis`. Current build:
3,085 LOW / 1,186 MEDIUM / 475 HIGH (of 4,746 scored persons).

## Feature importances (random forest)

Top drivers, in order: `prior_case_count`, `days_since_first_case`
(career length), `distinct_prior_crime_types`, `age`. Current crime type
(violent/property) and state matter far less than an offender's own
history - a criminologically unsurprising, and reassuring, result (the
model isn't leaning on demographic/geographic proxies).

## Endpoints (all require a Bearer token - see Authentication below)

| Endpoint | Min. role | Description |
|---|---|---|
| `GET /api/offender-profiling/model-info` | `ANALYST` | Model comparison, feature importances, censoring stats, risk-tier thresholds. |
| `GET /api/offender-profiling/person/{person_id}` | `INVESTIGATOR` | Precomputed risk profile for one accused person. |
| `GET /api/offender-profiling/risk-list?risk_tier=&limit=` | `INVESTIGATOR` | Persons at a given risk tier, sorted by predicted probability. |
| `GET /api/offender-profiling/predict?...` | `INVESTIGATOR` | Live inference against the trained model for a hypothetical profile - not a lookup. |

`/predict` is the one endpoint that actually runs the pickled sklearn
model at request time (all others serve the precomputed
`person_risk_scores.csv`) - useful for a "what if this new arrest had N
priors" investigator query.

## Authentication (pillar 10)

This was the first service wired into `auth-service`'s JWT-based RBAC, as
a concrete end-to-end proof before the same pattern was retrofitted into
every other service (see `backend/services/auth-service/README.md` for
the full per-service breakdown). Every endpoint requires
`Authorization: Bearer <token>`; person/case-level endpoints require at
least `INVESTIGATOR`, aggregate model info only requires `ANALYST`.

`app/rbac.py` verifies tokens statelessly using the same `JWT_SECRET` /
`JWT_ALGORITHM` env vars `auth-service` issues them with - no callback to
auth-service per request. Get a token:

```bash
curl -X POST http://localhost:8020/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "pi_sharma", "password": "<from build_demo_users.py output>"}'
```

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8016
```

Regenerate the model with:
```bash
python scripts/data_generation/offender_profiling/build_recidivism_model.py
```

## Tests

```bash
python -m pytest tests/ -v
```

## Deployment

See [docs/deployment/DEPLOY.md](../../../docs/deployment/DEPLOY.md) for the
Zoho Catalyst AppSail deploy guide (backend-only, no frontend yet).
