# explainable-ai

Explainable AI / transparent analytics (pillar 9).

## Why this service isn't seven separate explainers

Six of the seven analytics services in this platform are transparent by
construction, not by an add-on layer:

| Service | Already-transparent mechanism |
|---|---|
| `network-analysis` | Graph metrics (degree, community ID) - direct computation, no learned model. |
| `pattern-analytics` | DBSCAN/PCA+KMeans - unsupervised, reports the actual distance/component values. |
| `sociological-insights` | Plain Pearson correlation on real joined Census data. |
| `financial-crime-analysis` | Rule-based flags - every triggered rule is a visible boolean field. |
| `crime-forecasting` | Three interpretable models, backtested MAE reported for all candidates. |
| `investigator-decision-support` | Point-based score - the breakdown IS the explanation. |

**`offender-profiling` is the one exception**: its Random Forest recidivism
classifier is an actual black-box model - 200 trees of depth 6 aren't
reducible to a formula a person can read. That's the one place real
post-hoc explanation earns its keep, and it's what this platform's research
doc calls out explicitly (SHAP values for predictive risk-scoring models).
`GET /api/explainability/methodology` reports the full table above so a
caller doesn't have to go find each service's README to see this.

## What this service actually adds: real, validated SHAP explanations

Uses `shap.TreeExplainer` against offender-profiling's actual trained
model - **exact** Shapley values for tree ensembles (it walks the real
trees; no sampling/approximation the way `KernelExplainer` would need for
an arbitrary black-box model).

This is computed against `person_feature_vectors.csv`, a new output added
to `build_recidivism_model.py` specifically for this: the literal feature
matrix that produced `person_risk_scores.csv`, not a second,
independently-reconstructed feature matrix that could silently drift from
what was actually predicted.

**Validated, not assumed:**
- Every person's SHAP values are checked to reconstruct their actual
  predicted probability (`base_value + sum(shap_values) == predict_proba`).
  Max reconstruction error across all 4,746 scored persons: **5.9e-15**
  (floating-point noise, not an approximation gap).
- Global SHAP importance (mean `|SHAP|` across all persons) is compared
  against the Random Forest's own built-in `feature_importances_` via
  Spearman rank correlation: **0.949**. These two numbers are computed from
  entirely different definitions of "important" (game-theoretic attribution
  of real predictions vs. mean impurity decrease during training) and
  needn't agree - the strong correlation is corroborating evidence the
  model isn't leaning on some feature training-time impurity overweights
  but which barely moves real predictions, not a redundant recomputation.

Top 5 SHAP drivers on the current build: `prior_case_count`,
`distinct_prior_crime_types`, `days_since_first_case`, `state_OTHER`,
`age` - matching offender-profiling's own README almost exactly (an
offender's own history dominates, not demographic/geographic proxies).

## Why it reads offender-profiling's files directly

Same tradeoff `investigator-decision-support` documents in its own
README: this service reads `model.pkl`, `feature_metadata.json`, and
`person_risk_scores.csv` straight from
`data/processed/offender-profiling/` rather than calling
offender-profiling over HTTP per request. One source of truth for the
actual classifier, no duplicated model file, and this service still works
if offender-profiling's API isn't running.

## Endpoints (all require `Authorization: Bearer <token>` - see auth-service)

| Endpoint | Min. role | Description |
|---|---|---|
| `GET /api/explainability/methodology` | `ANALYST` | The transparency-mechanism table above, as structured data. |
| `GET /api/explainability/model-info` | `ANALYST` | Global SHAP feature importance + concordance check against the RF's built-in importances. |
| `GET /api/explainability/person/{person_id}` | `INVESTIGATOR` | One accused person's real local SHAP explanation - which specific factors pushed their actual prediction up or down, and by how much. |
| `GET /api/explainability/predict-explain?...` | `ANALYST` | Live SHAP against a **hypothetical** profile (no real person) - mirrors offender-profiling's own `/predict`, but returns the feature-by-feature reasoning instead of just a number. |

`/person/{id}` explains a real, already-computed prediction (precomputed
SHAP values, see below); `/predict-explain` runs `TreeExplainer` live
against whatever inputs are passed in - useful for "why would this
hypothetical arrest profile score this way" investigator/analyst queries,
without naming a real person (stays at `ANALYST`, unlike offender-profiling's
own `/predict` which is `INVESTIGATOR` since decision-support flows
sometimes pass a real person's current profile through it).

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8021
```

Regenerate SHAP explanations with (requires offender-profiling's
`build_recidivism_model.py` to have been run first, since it produces
`person_feature_vectors.csv`):
```bash
python scripts/data_generation/offender_profiling/build_recidivism_model.py
python scripts/data_generation/explainability/build_shap_explanations.py
```

## Tests

```bash
python -m pytest tests/ -v
```

## Deployment

See [docs/deployment/DEPLOY.md](../../../docs/deployment/DEPLOY.md) for the
Zoho Catalyst AppSail deploy guide (backend-only, no frontend yet).
