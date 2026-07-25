"""
Crime forecasting (pillar 8) on real NCRB district-wise annual IPC crime
data (data/raw/ncrb-india-crime/district-wise/, 2001-2012, the same source
calibrate_ncrb.py uses). This is real historical time series, not
NCRB-calibrated synthetic data - the forecasts and backtest numbers below
are computed from actual reported crime counts.

Methodology, and why it's kept deliberately simple:
  - Only 12 annual points per district exist. That's too short a series for
    ARIMA/Prophet-style models to fit reliably (they'd overfit noise, not
    signal, on 9 training points) - so this uses three transparent,
    auditable models instead: NAIVE (last value), MOVING_AVERAGE (mean of
    last 3 years), and LINEAR_TREND (OLS). Simpler than what pillar 9
    ("explainable AI") will eventually want to show off, but a model nobody
    can explain from 12 data points is worse than an honest, inspectable one.
  - Backtested with an actual train/test split: fit on 2001-2009, evaluate
    against the real observed 2010-2012 (MAE, MAPE). NAIVE is included
    specifically as a baseline - if LINEAR_TREND or MOVING_AVERAGE can't
    beat "predict no change from last year," that's the honest result to
    report, not something to hide. See eval_stats.json / README for how
    often each model actually wins.
  - The best-by-backtest-MAE model per (district, series) is then refit on
    the FULL 2001-2012 history to produce the actual 2013-2015 forecast
    shipped to the service - backtesting and the shipped forecast use
    different fit windows on purpose (you always want the final model
    trained on all available real data, backtesting is only to pick which
    model family to trust).

Crime-type groupings reuse the exact category names from
backend/services/pattern-analytics/app/taxonomy.py (VIOLENT_TYPES /
PROPERTY_TYPES) so "violent crime" means the same thing across pillars.
Kept as a separate literal copy here rather than a shared import, matching
the existing precedent (taxonomy.py's own docstring notes it mirrors
scripts/data_generation/crime_type_profiles.py the same way).

Outputs (data/processed/forecasting/):
    district_forecasts.csv  - one row per (district, series): backtest
                               metrics for all 3 models, the selected
                               model, and the 2013/2014/2015 forecast
    forecast_stats.json     - methodology summary: districts included/
                               excluded, per-model win-rate, aggregate
                               backtest accuracy

Usage:
    python scripts/data_generation/forecasting/build_crime_forecasts.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibrate_ncrb import CRIME_TYPE_MAP, load_clean  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data" / "processed" / "forecasting"

TRAIN_YEARS = list(range(2001, 2010))   # 2001-2009
TEST_YEARS = list(range(2010, 2013))    # 2010-2012 (held out, real backtest)
ALL_YEARS = list(range(2001, 2013))     # 2001-2012 (full history, final fit)
FORECAST_YEARS = [2013, 2014, 2015]

# Mirrors backend/services/pattern-analytics/app/taxonomy.py - see docstring.
VIOLENT_CODES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY",
    "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY",
}
PROPERTY_CODES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}

VIOLENT_RAW_COLUMNS = [raw for raw, code in CRIME_TYPE_MAP.items() if code in VIOLENT_CODES]
PROPERTY_RAW_COLUMNS = [raw for raw, code in CRIME_TYPE_MAP.items() if code in PROPERTY_CODES]


def build_series_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (state, district, year) with TOTAL/VIOLENT/PROPERTY counts."""
    work = df.copy()
    work["VIOLENT"] = work[VIOLENT_RAW_COLUMNS].sum(axis=1)
    work["PROPERTY"] = work[PROPERTY_RAW_COLUMNS].sum(axis=1)
    work["TOTAL"] = work["TOTAL IPC CRIMES"]
    return work[["STATE/UT", "DISTRICT", "YEAR", "TOTAL", "VIOLENT", "PROPERTY"]]


def _fit_naive(train_values: np.ndarray, horizon: int) -> np.ndarray:
    return np.full(horizon, train_values[-1], dtype=float)


def _fit_moving_average(train_values: np.ndarray, horizon: int, window: int = 3) -> np.ndarray:
    avg = train_values[-window:].mean()
    return np.full(horizon, avg, dtype=float)


def _fit_linear_trend(train_years: np.ndarray, train_values: np.ndarray, forecast_years: np.ndarray) -> np.ndarray:
    slope, intercept = np.polyfit(train_years, train_values, 1)
    preds = slope * forecast_years + intercept
    return np.clip(preds, a_min=0, a_max=None)


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    nonzero = actual != 0
    if not nonzero.any():
        return None
    return float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100)


def forecast_one_series(years: np.ndarray, values: np.ndarray) -> dict:
    train_mask = np.isin(years, TRAIN_YEARS)
    test_mask = np.isin(years, TEST_YEARS)
    train_years, train_values = years[train_mask], values[train_mask]
    test_years, test_values = years[test_mask], values[test_mask]
    horizon = len(TEST_YEARS)

    candidates = {
        "NAIVE": _fit_naive(train_values, horizon),
        "MOVING_AVERAGE": _fit_moving_average(train_values, horizon),
        "LINEAR_TREND": _fit_linear_trend(train_years, train_values, np.array(TEST_YEARS, dtype=float)),
    }
    backtest = {name: {"mae": _mae(test_values, preds), "mape": _mape(test_values, preds)}
                for name, preds in candidates.items()}
    selected_model = min(backtest, key=lambda name: backtest[name]["mae"])

    # Refit the selected model family on the FULL history for the real forecast.
    forecast_years_arr = np.array(FORECAST_YEARS, dtype=float)
    if selected_model == "NAIVE":
        forecast_values = _fit_naive(values, len(FORECAST_YEARS))
    elif selected_model == "MOVING_AVERAGE":
        forecast_values = _fit_moving_average(values, len(FORECAST_YEARS))
    else:
        forecast_values = _fit_linear_trend(years.astype(float), values, forecast_years_arr)

    return {
        "selected_model": selected_model,
        "backtest": backtest,
        "forecast": {str(y): round(float(v), 1) for y, v in zip(FORECAST_YEARS, forecast_values)},
        "last_observed_year": int(years.max()),
        "last_observed_value": float(values[years.argmax()]),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_clean()
    series_table = build_series_table(df)

    year_counts = series_table.groupby(["STATE/UT", "DISTRICT"])["YEAR"].nunique()
    complete_districts = set(year_counts[year_counts == 12].index)
    total_districts = len(year_counts)

    rows = []
    win_counts = {"NAIVE": 0, "MOVING_AVERAGE": 0, "LINEAR_TREND": 0}
    for (state, district), group in series_table.groupby(["STATE/UT", "DISTRICT"]):
        if (state, district) not in complete_districts:
            continue
        group = group.sort_values("YEAR")
        years = group["YEAR"].to_numpy()
        for series_name in ["TOTAL", "VIOLENT", "PROPERTY"]:
            values = group[series_name].to_numpy(dtype=float)
            result = forecast_one_series(years, values)
            win_counts[result["selected_model"]] += 1
            rows.append({
                "state": state,
                "district": district,
                "series": series_name,
                "selected_model": result["selected_model"],
                "backtest_mae": round(result["backtest"][result["selected_model"]]["mae"], 2),
                "backtest_mape": result["backtest"][result["selected_model"]]["mape"],
                "naive_backtest_mae": round(result["backtest"]["NAIVE"]["mae"], 2),
                "linear_trend_backtest_mae": round(result["backtest"]["LINEAR_TREND"]["mae"], 2),
                "moving_average_backtest_mae": round(result["backtest"]["MOVING_AVERAGE"]["mae"], 2),
                "last_observed_year": result["last_observed_year"],
                "last_observed_value": result["last_observed_value"],
                "forecast_2013": result["forecast"]["2013"],
                "forecast_2014": result["forecast"]["2014"],
                "forecast_2015": result["forecast"]["2015"],
            })

    forecasts = pd.DataFrame(rows)
    forecasts.to_csv(OUT_DIR / "district_forecasts.csv", index=False)

    n_series = len(forecasts)
    beats_naive = int((forecasts["selected_model"] != "NAIVE").sum())
    stats = {
        "total_ncrb_districts": total_districts,
        "districts_with_complete_2001_2012_history": len(complete_districts),
        "districts_excluded_incomplete_history": total_districts - len(complete_districts),
        "series_forecast": n_series,
        "train_years": TRAIN_YEARS,
        "test_years": TEST_YEARS,
        "forecast_years": FORECAST_YEARS,
        "model_win_counts": win_counts,
        "series_where_naive_was_beaten": beats_naive,
        "series_where_naive_was_beaten_pct": round(beats_naive / n_series * 100, 1) if n_series else 0.0,
        "mean_backtest_mae_by_model": {
            "NAIVE": round(forecasts["naive_backtest_mae"].mean(), 2),
            "LINEAR_TREND": round(forecasts["linear_trend_backtest_mae"].mean(), 2),
            "MOVING_AVERAGE": round(forecasts["moving_average_backtest_mae"].mean(), 2),
        },
    }
    (OUT_DIR / "forecast_stats.json").write_text(json.dumps(stats, indent=2))

    print(f"NCRB districts: {total_districts}")
    print(f"Complete 2001-2012 history: {len(complete_districts)} ({len(complete_districts)/total_districts:.1%})")
    print(f"Series forecast: {n_series} ({len(complete_districts)} districts x 3 series)")
    print(f"Model win counts: {win_counts}")
    print(f"Naive beaten in {beats_naive}/{n_series} series ({stats['series_where_naive_was_beaten_pct']}%)")
    print(f"Mean backtest MAE by model: {stats['mean_backtest_mae_by_model']}")
    print(f"\nWrote {OUT_DIR / 'district_forecasts.csv'}")
    print(f"Wrote {OUT_DIR / 'forecast_stats.json'}")


if __name__ == "__main__":
    main()
