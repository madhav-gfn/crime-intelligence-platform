"""
Loads the precomputed census-x-crime district join (see
scripts/data_generation/sociology/build_district_join.py) and serves
correlation/ranking/scatter views over it.

ALLOWED_INDICATORS is the single gate that decides what can ever be
correlated against a crime-rate metric. sc_st_share and the religion-share
columns exist in the source data and are returned by district_profile() for
transparency, but they are not in this list - so correlations(), rankings(),
and scatter() structurally cannot use them, the same way
oltp/etl_to_analytics.py's ensure_person() has no caste/religion parameter.
This isn't a runtime check that could be bypassed by a bad request; the
demographic columns are simply never looked up through this path. See the
README for why (ecological-fallacy risk in a policing-facing tool).
"""
import json
from pathlib import Path

import pandas as pd
from scipy import stats

from app.config import settings

ALLOWED_INDICATORS = [
    "literacy_rate",
    "urbanization_rate",
    "workforce_participation_rate",
    "higher_education_rate",
    "amenity_index",
]

CRIME_METRICS = [
    "crime_rate_per_100k",
    "violent_crime_rate_per_100k",
    "property_crime_rate_per_100k",
    "violent_ratio",
    "property_ratio",
]

DEMOGRAPHIC_CONTEXT_ONLY = ["sc_st_share", "hindu_share", "muslim_share", "christian_share", "sikh_share"]


def _interpret(r: float, p: float) -> str:
    if p >= 0.05:
        return "not statistically significant (p >= 0.05)"
    strength = "weak"
    if abs(r) >= 0.5:
        strength = "strong"
    elif abs(r) >= 0.3:
        strength = "moderate"
    direction = "positive" if r > 0 else "negative"
    return f"{strength} {direction} correlation (p < 0.05)"


class AnalyticsStore:
    def __init__(self, data_path: Path, stats_path: Path):
        self.data_path = data_path
        self.stats_path = stats_path
        self.df: pd.DataFrame | None = None
        self.match_stats: dict = {}

    def load(self):
        self.df = pd.read_csv(self.data_path)
        self.match_stats = json.loads(self.stats_path.read_text()) if self.stats_path.exists() else {}
        return self

    def districts(self) -> dict:
        n = len(self.df)
        total_census = self.match_stats.get("total_census_districts", n)
        rows = self.df.sort_values("crime_rate_per_100k", ascending=False)
        return {
            "total_census_districts": total_census,
            "matched_districts": n,
            "match_rate": round(n / total_census, 4) if total_census else 0.0,
            "districts": [
                {
                    "state": r["state"],
                    "district": r["district"],
                    "match_type": r["match_type"],
                    "population": int(r["population"]),
                    "crime_rate_per_100k": r["crime_rate_per_100k"],
                }
                for _, r in rows.iterrows()
            ],
        }

    def district_profile(self, district: str) -> dict | None:
        district_lower = district.lower()
        matches = self.df[self.df["district"].str.lower() == district_lower]
        if matches.empty:
            matches = self.df[self.df["district"].str.lower().str.contains(district_lower, regex=False)]
        if matches.empty:
            return None
        row = matches.iloc[0]
        return {col: (row[col].item() if hasattr(row[col], "item") else row[col]) for col in self.df.columns}

    def correlations(self, min_population: int = 0) -> dict:
        df = self.df[self.df["population"] >= min_population]
        results = []
        for indicator in ALLOWED_INDICATORS:
            for metric in CRIME_METRICS:
                pair = df[[indicator, metric]].dropna()
                if len(pair) < 10:
                    continue
                r, p = stats.pearsonr(pair[indicator], pair[metric])
                results.append({
                    "indicator": indicator,
                    "crime_metric": metric,
                    "pearson_r": round(float(r), 4),
                    "p_value": round(float(p), 6),
                    "n": len(pair),
                    "interpretation": _interpret(r, p),
                })
        results.sort(key=lambda x: -abs(x["pearson_r"]))
        return {
            "districts_included": len(df),
            "indicators_used": ALLOWED_INDICATORS,
            "crime_metrics_used": CRIME_METRICS,
            "excluded_fields_note": (
                "sc_st_share and religion-share fields are present in district profiles as public-census "
                "context but are never correlated against crime rates here - district-level correlation of "
                "caste/religion composition with crime is an ecological-fallacy risk, not a defensible signal. "
                "See this service's README."
            ),
            "results": results,
        }

    def rankings(self, sort_by: str, order: str = "desc", limit: int = 20, min_population: int = 0) -> dict:
        df = self.df[self.df["population"] >= min_population]
        ascending = order == "asc"
        df = df.sort_values(sort_by, ascending=ascending).head(limit)
        return {
            "sort_by": sort_by,
            "order": order,
            "limit": limit,
            "districts": [
                {
                    "state": r["state"],
                    "district": r["district"],
                    "value": r[sort_by],
                    "population": int(r["population"]),
                    "crime_rate_per_100k": r["crime_rate_per_100k"],
                }
                for _, r in df.iterrows()
            ],
        }

    def scatter(self, indicator: str, crime_metric: str) -> dict:
        pair = self.df[["state", "district", "population", indicator, crime_metric]].dropna()
        return {
            "indicator": indicator,
            "crime_metric": crime_metric,
            "points": [
                {
                    "state": r["state"],
                    "district": r["district"],
                    "x": r[indicator],
                    "y": r[crime_metric],
                    "population": int(r["population"]),
                }
                for _, r in pair.iterrows()
            ],
        }


store = AnalyticsStore(settings.district_data_path, settings.match_stats_path)
