# sociological-insights

Sociological crime insights (pillar 4). Unlike `network-analysis` and
`pattern-analytics`, which run entirely on the synthetic-but-NCRB-calibrated
seed dataset, this service joins **two real datasets**: the actual 2011
Census district socioeconomic figures and NCRB-calibrated district-level
crime rates (individual FIRs are synthetic, but the district crime *volume
and mix* they're sampled from is real — see
`data/schemas/synthetic_fir_schema.md`).

## Data pipeline

```
data/raw/india-census-2011/          data/seed/fir.csv
india-districts-census-2011.csv      (OLTP+ETL output)
        |                                    |
        +------------------+-----------------+
                           v
scripts/data_generation/sociology/build_district_join.py
   - normalizes (state, district) names on both sides
   - matches census districts to fir.csv districts
     (exact match after suffix-stripping, else difflib
     fuzzy match >= 0.82 within the same state)
   - computes literacy/urbanization/workforce/education/
     amenity indicators from raw census counts
   - computes crime_rate_per_100k etc. using real census
     population as the denominator (fixes a gap in
     pattern-analytics, which never normalizes by population)
                           v
data/processed/sociology/district_socioeconomic_crime.csv
data/processed/sociology/match_stats.json
                           v
                  this service (loads the CSV at startup)
```

Regenerate with:
```bash
python scripts/data_generation/sociology/build_district_join.py
```

## Match rate — read this before trusting a number

District-name matching across two independently-sourced datasets is
inherently approximate. On the current 5,000-case seed dataset:

- **505 / 640 census districts matched (78.9%)** — 435 exact (after
  suffix-normalization), 70 fuzzy (difflib ratio >= 0.82).
- 135 census districts have no corresponding crime-data district and are
  **dropped**, not backfilled with a guess. `/api/sociology/districts`
  reports the live match rate on every call via `match_stats.json`.
- Per-district FIR counts are small (5,000 cases / 661 crime-data districts
  over 5 years) — treat `total_crimes`/rate columns as directional, not
  precise, the same caveat `pattern-analytics` documents for its sparse
  per-cell counts.

## Attribute decoupling: what's excluded from correlations, and why

The census provides SC/ST population share and religion composition per
district. These are **not** used anywhere in `/correlations`, `/rankings`,
or `/scatter` — they're carried through `district_socioeconomic_crime.csv`
and returned by `/district/{district}` purely as public-census context.

The reason: correlating *aggregate* caste/religion composition against
*aggregate* crime rate at the district level is a classic ecological
fallacy — even a real statistical correlation at that level says nothing
about individual behavior, and presenting it in a policing-facing tool
invites exactly the "this community is more criminal" misreading the
platform's own research doc warns against (see the COMPAS bias discussion,
and the caste/religion decoupling already enforced in
`scripts/data_generation/oltp/etl_to_analytics.py`'s `ensure_person()`).

This is enforced structurally, not by convention: `ALLOWED_INDICATORS` in
`app/analytics_store.py` is the only list `/correlations`, `/rankings`, and
`/scatter` ever read from, and it contains five structural/economic
indicators only. `DEMOGRAPHIC_CONTEXT_ONLY` is a separate list never passed
to `stats.pearsonr`, ranking, or scatter code paths — a request for
`sort_by=sc_st_share` or `/scatter/muslim_share` gets a 400, not a computed
result (see `tests/test_sociology_api.py`).

## Interpreting the correlations that *are* computed

Even the allowed indicators (literacy, urbanization, workforce
participation, higher education, household amenities) show only **weak**
positive correlations (r ≈ 0.19–0.29) with crime-rate-per-100k in the
current data, despite large sample sizes making them statistically
significant (p < 0.05 at n≈505). A plausible reading — consistent with
real criminology literature — is that more literate/urbanized districts
have **higher reporting rates**, not necessarily more underlying crime;
this service surfaces the correlation, it does not (and should not) claim
a causal direction. Present it that way in any demo.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/sociology/districts` | All matched districts with crime rate, sorted descending. Includes match-rate summary. |
| `GET /api/sociology/district/{district}` | Full socioeconomic + crime profile for one district (case-insensitive, substring fallback). |
| `GET /api/sociology/correlations?min_population=` | Pearson r + p-value for each of 5 indicators x 5 crime metrics. |
| `GET /api/sociology/rankings?sort_by=&order=&limit=&min_population=` | Districts ranked by any allowed indicator or crime metric. |
| `GET /api/sociology/scatter/{indicator}?crime_metric=` | Raw (x, y) pairs for frontend scatter plots. |

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8012
```

## Tests

```bash
python -m pytest tests/ -v
```
