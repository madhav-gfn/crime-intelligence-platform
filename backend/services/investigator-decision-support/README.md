# investigator-decision-support

Investigator decision support (pillar 6). Unlike the other five services,
this one isn't a new analytics engine — it's a **synthesis layer** over
signals the other five already compute: network-analysis's co-accused
graph, pattern-analytics's case-volume signal (reimplemented lightly, see
below), sociological-insights's real Census correlation, crime-forecasting's
backtested trend, and offender-profiling's trained risk model.

## Why it reads files instead of calling the other services

This service reads the same precomputed artifacts the other services
read/produce (`data/seed/*.csv`,
`data/processed/offender-profiling/person_risk_scores.csv`,
`data/processed/forecasting/district_forecasts.csv`,
`data/processed/sociology/district_socioeconomic_crime.csv`) directly,
rather than making live HTTP calls to five running services. That's a
deliberate tradeoff, not a shortcut:

- **Demo reliability**: this service doesn't go down if one of the other
  five isn't running.
- **Graceful degradation**: a district missing from the sociology or
  forecasting join (see those services' README for real match-rate
  numbers - 78.9% and 77.1% respectively) returns `available: false` for
  that one field instead of failing the whole request.
- **Honest about the real production answer**: a real version of this
  pillar would eventually want an event stream or a shared warehouse
  table behind it, not synchronous fan-out calls per request. Reading the
  same files is closer to that shape than HTTP fan-out would have been.

There's also no separate offline prep script here, unlike the other five
pillars — case-priority scoring is simple arithmetic over ~5,000 rows and
runs once at service startup (`analytics_store.py`'s `load()`), not a
multi-minute batch job like the AML or NCRB-forecasting pipelines.

## Case priority: a transparent point-based score, not a black box

Every **unresolved** case (`UNDER_INVESTIGATION` or `TRIAL`, 1,825 of
5,000 cases) gets scored on four components:

| Component | Points | Trigger |
|---|---|---|
| Violent crime | +3 | `crime_type_code` in the violent-crime set (same taxonomy as pattern-analytics/crime-forecasting) |
| Accused risk | +2 / +1 | Any accused person on the case has a HIGH / MEDIUM offender-profiling risk tier |
| District hotspot | +2 | District is in the top quartile (>= P75) by total case volume — a simplified proxy for pattern-analytics's DBSCAN density clusters, not a reimplementation of them |
| Stale | +1 | Case age > 180 days from the dataset's reference date (its max `date_reported`, **not** wall-clock today — this is 2020-2024 historical demo data, not a live docket) |

`priority_score` (0-8) maps to `priority_tier`: **HIGH** >= 6, **MEDIUM**
4-5, **LOW** <= 3 — thresholds picked by checking the real score
distribution first (265 HIGH / 638 MEDIUM / 922 LOW on the current build),
not guessed blind. Every component is a visible field on the response, not
folded into an opaque total.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/decision-support/stats` | Unresolved-case counts, tier distribution, staleness threshold. |
| `GET /api/decision-support/case-priority?priority_tier=&limit=` | Ranked unresolved cases with full score breakdown. |
| `GET /api/decision-support/case/{fir_id}` | One case's priority breakdown. 404 distinguishes "doesn't exist" from "exists but is resolved, not in the queue." |
| `GET /api/decision-support/person-dossier/{person_id}` | Cross-pillar profile: offender-profiling risk score, network-analysis co-accused associates + degree, full case history. |
| `GET /api/decision-support/district-briefing/{district}` | Case volume/hotspot status + real Census socioeconomic context + real backtested crime forecast, joined in one place. |

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8018
```

Requires `data/processed/offender-profiling/person_risk_scores.csv`,
`data/processed/forecasting/district_forecasts.csv`, and
`data/processed/sociology/district_socioeconomic_crime.csv` to already
exist — run those three services' prep scripts first if starting from a
clean checkout.

## Tests

```bash
python -m pytest tests/ -v
```
