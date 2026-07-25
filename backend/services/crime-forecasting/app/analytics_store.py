"""
Loads the precomputed, backtested district forecasts built by
scripts/data_generation/forecasting/build_crime_forecasts.py from real NCRB
2001-2012 district-wise crime data. No model fitting happens at request
time - everything here is a lookup over the precomputed table, the same
"heavy lifting offline, serve the artifact" pattern as the other services'
calibration/join steps.
"""
import json
from pathlib import Path

import pandas as pd

from app.config import settings

VALID_SERIES = {"TOTAL", "VIOLENT", "PROPERTY"}


class AnalyticsStore:
    def __init__(self, forecasts_path: Path, forecast_stats_path: Path):
        self.forecasts_path = forecasts_path
        self.forecast_stats_path = forecast_stats_path
        self.df: pd.DataFrame | None = None
        self.forecast_stats: dict = {}

    def load(self):
        self.df = pd.read_csv(self.forecasts_path)
        self.forecast_stats = json.loads(self.forecast_stats_path.read_text())
        self.df["pct_change"] = (
            (self.df["forecast_2015"] - self.df["last_observed_value"])
            / self.df["last_observed_value"].replace(0, pd.NA)
            * 100
        )
        return self

    def stats(self) -> dict:
        return self.forecast_stats

    def _series_row_to_dict(self, row: pd.Series) -> dict:
        return {
            "series": row["series"],
            "selected_model": row["selected_model"],
            "backtest_mae": row["backtest_mae"],
            "backtest_mape": None if pd.isna(row["backtest_mape"]) else row["backtest_mape"],
            "naive_backtest_mae": row["naive_backtest_mae"],
            "linear_trend_backtest_mae": row["linear_trend_backtest_mae"],
            "moving_average_backtest_mae": row["moving_average_backtest_mae"],
            "last_observed_year": int(row["last_observed_year"]),
            "last_observed_value": row["last_observed_value"],
            "forecast_2013": row["forecast_2013"],
            "forecast_2014": row["forecast_2014"],
            "forecast_2015": row["forecast_2015"],
        }

    def district_forecast(self, district: str) -> dict | None:
        district_lower = district.lower()
        matches = self.df[self.df["district"].str.lower() == district_lower]
        if matches.empty:
            matches = self.df[self.df["district"].str.lower().str.contains(district_lower, regex=False)]
        if matches.empty:
            return None
        # multiple districts can substring-match (e.g. "BANGALORE" -> 2
        # real districts) - pin to whichever one matched first alphabetically,
        # same fallback convention as the other services' profile lookups.
        first_match_name = sorted(matches["district"].unique())[0]
        group = matches[matches["district"] == first_match_name]
        state = group.iloc[0]["state"]
        return {
            "state": state,
            "district": first_match_name,
            "series": [self._series_row_to_dict(row) for _, row in group.iterrows()],
        }

    def rankings(self, series: str = "TOTAL", order: str = "desc", limit: int = 20) -> dict:
        df = self.df[self.df["series"] == series].dropna(subset=["pct_change"])
        ascending = order == "asc"
        df = df.sort_values("pct_change", ascending=ascending).head(limit)
        return {
            "series": series,
            "order": order,
            "limit": limit,
            "districts": [
                {
                    "state": r["state"],
                    "district": r["district"],
                    "last_observed_value": r["last_observed_value"],
                    "forecast_2015": r["forecast_2015"],
                    "pct_change": round(r["pct_change"], 2),
                    "selected_model": r["selected_model"],
                    "backtest_mae": r["backtest_mae"],
                }
                for _, r in df.iterrows()
            ],
        }


store = AnalyticsStore(settings.forecasts_path, settings.forecast_stats_path)
