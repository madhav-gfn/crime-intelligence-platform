# crime-forecasting

Crime forecasting (pillar 8). Like `sociological-insights`, this runs on
**real historical data** — the same NCRB district-wise IPC crime dataset
(`data/raw/ncrb-india-crime/district-wise/`, 2001-2012, real reported
counts) that `calibrate_ncrb.py` uses to calibrate the synthetic FIR
generator — not synthetic FIRs themselves. Every forecast on this service
is backed by a genuine backtest against real held-out years, not a curve
fit nobody checked.

## Why the models are deliberately simple

Each district only has 12 annual data points. That's far too short a
series to fit ARIMA/Prophet-style models reliably — on 9 training points
they'd fit noise, not signal, and produce forecasts that look
sophisticated but aren't trustworthy. Instead this uses three transparent,
inspectable models per (district, series):

| Model | What it predicts |
|---|---|
| `NAIVE` | Next years = last observed year (no change) |
| `MOVING_AVERAGE` | Next years = mean of the last 3 observed years |
| `LINEAR_TREND` | Next years = OLS trend line extrapolated forward |

## Methodology: a real backtest, not a vibe

For every (district, series) pair with complete 2001-2012 data:
1. **Train** each of the 3 models on 2001-2009 only.
2. **Test**: predict 2010-2012 and compare against the *actual* real NCRB
   counts for those years (MAE, MAPE).
3. **Select** whichever model had the lowest backtest MAE.
4. **Refit** that selected model family on the *full* 2001-2012 history
   (more data = better final fit) to produce the shipped 2013-2015
   forecast. Backtesting and the shipped forecast intentionally use
   different fit windows — backtesting exists only to pick which model
   family to trust, not to be the forecast itself.

## The honest finding: naive is a surprisingly strong baseline

Across all 1,914 forecast series (638 districts x 3 series):

| Model | Selected as best | Mean backtest MAE |
|---|---|---|
| NAIVE | 821 (42.9%) | **255.2** (lowest) |
| MOVING_AVERAGE | 567 (29.6%) | 286.9 |
| LINEAR_TREND | 526 (27.5%) | 316.7 |

NAIVE is beaten by a smarter model in 57.1% of individual series, but has
the lowest *average* error across all series — meaning district-level
annual crime counts don't trend as strongly or consistently as a linear
model assumes, and "predict no change from last year" is a legitimately
hard baseline to beat over a single decade. This is reported directly
rather than hidden: it's a real methodological finding, consistent with
general time-series forecasting folklore, and it's exactly why this
service picks the best model *per series* via backtesting instead of
hardcoding one model for every district.

## Data completeness

189 of 827 NCRB districts (22.9%) don't have all 12 years present — mostly
due to district boundary changes / new districts formed mid-period (a real
data-quality issue, not a bug). Those districts are excluded entirely
rather than backfilled with a guess. `/api/forecasting/stats` reports the
live completeness numbers.

## Crime-type groupings

`VIOLENT` and `PROPERTY` series use the same category definitions as
`backend/services/pattern-analytics/app/taxonomy.py` (kept as a separate
literal copy per that module's own precedent, not a shared import) — so
"violent crime" means the same thing whether you're looking at hotspot
clusters or a 2015 forecast.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/forecasting/stats` | Dataset completeness, model win-rates, mean backtest error by model. |
| `GET /api/forecasting/district/{district}` | TOTAL/VIOLENT/PROPERTY forecasts + backtest metrics for one district. |
| `GET /api/forecasting/rankings?series=&order=&limit=` | Districts ranked by predicted 2015 % change from last observed year. |

All endpoints require `Authorization: Bearer <token>` with at least the
`ANALYST` role (see `backend/services/auth-service/README.md`) - this
service is entirely district-level forecast data, no person/account
identifiers anywhere. Tokens are verified statelessly via `app/rbac.py`.

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8014
```

## Tests

```bash
python -m pytest tests/ -v
```
