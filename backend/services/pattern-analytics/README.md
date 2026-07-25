# Pattern Analytics Service

FastAPI service for pillar 3 (Crime Pattern & Trend Analytics): geospatial
hotspot clustering, district severity tiering, temporal trend analysis,
emerging-spike early warning, and MO-similarity case matching.

Approach follows `docs/architecture/Conversational Crime Analytics AI
Research.md`'s "Geospatial-Temporal Crime Pattern Analytics" section: DBSCAN
for hotspots, PCA+KMeans for district severity. Runs on the calibrated
synthetic seed dataset in `data/seed/` (see
`data/schemas/synthetic_fir_schema.md` for what's real vs. synthetic).

## Setup

```bash
cd backend/services/pattern-analytics
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
```

## Run

```bash
./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8011
```

Docs at `http://127.0.0.1:8011/docs`.

## Test

```bash
./.venv/Scripts/python -m pytest tests/ -v
```

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/patterns/stats` | Dataset-wide summary (crime-type counts, date range, district count) |
| `GET /api/patterns/hotspots` | DBSCAN geospatial clustering, filterable by crime type/district/date range, tunable `eps_km`/`min_points` |
| `GET /api/patterns/district-severity` | PCA(2)+KMeans(3) tiering of districts into LOW/MEDIUM/HIGH severity on a 5-feature vector (volume, violent ratio, property ratio, unresolved ratio, crime-type diversity) |
| `GET /api/patterns/trends/{granularity}` | `monthly`, `weekday`, or `hourly` incident counts, filterable by crime type/district |
| `GET /api/patterns/emerging` | Flags (district, crime_type) pairs whose recent-window count is well above their baseline-implied rate - a lightweight early-warning signal |
| `GET /api/patterns/similar-cases/{fir_id}` | Cosine-similarity MO matching against crime type + weapon + time-of-day, with `matching_features` listed per result for explainability |

## Two things worth knowing before trusting the output

1. **`geo_precise_fraction` on every hotspot cluster.** Roughly a third of
   districts in the seed data have real curated coordinates; the rest fall
   back to a deterministic jittered point near their state capital (see the
   schema doc). Because that jitter is per-district (not per-record), DBSCAN
   can trivially "cluster" every incident from a single low-volume district -
   this field tells you how much of a given cluster rests on real geocoding
   vs. that fallback, so it doesn't get mistaken for a genuine intra-district
   hotspot.
2. **`emerging` alert thresholds are tuned for this dataset's density**, not
   real case volume. ~5k FIRs spread across ~660 districts x 21 crime types
   over 5 years makes most (district, crime_type, 90-day-window) cells sparse
   by construction - the default `min_recent_count=3` reflects that. Turn it
   back up once this runs against real or higher-volume data.
