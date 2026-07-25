"""
Synthesis layer (pillar 6) over the six analytics services that already
exist, rather than a seventh siloed one. Reads the SAME precomputed
artifacts those services read/produce directly - data/seed/*.csv,
data/processed/offender-profiling/person_risk_scores.csv,
data/processed/forecasting/district_forecasts.csv,
data/processed/sociology/district_socioeconomic_crime.csv - instead of
making live HTTP calls to those services.

That's a deliberate choice, not a shortcut: a live-HTTP-fan-out design
would make this service's every response depend on five other services
being up simultaneously, which is a fragile demo story and a worse
production story (this is exactly the kind of aggregation a real
investigator-decision-support layer would eventually want backed by an
event stream or a shared warehouse table, not synchronous fan-out calls
per request). Reading the same files directly means this service degrades
gracefully (see SocioeconomicContext/ForecastContext.available) instead of
failing outright when a district isn't in one of the joined datasets.

Unlike the other five services, there is no separate offline prep script
here - case-priority scoring is simple arithmetic over ~5,000 rows and
runs once at startup in load(), not a multi-minute batch job like the AML
or NCRB-forecasting pipelines.
"""
from pathlib import Path

import pandas as pd

from app.config import settings

VIOLENT_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY",
    "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY",
}
PROPERTY_TYPES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}
UNRESOLVED_STATUSES = {"UNDER_INVESTIGATION", "TRIAL"}

DISTRICT_HOTSPOT_PERCENTILE = 0.75
PRIORITY_TIER_THRESHOLDS = {"HIGH": 6, "MEDIUM": 4}  # LOW is anything below MEDIUM's floor

_RISK_POINTS = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


class AnalyticsStore:
    def __init__(self, data_seed_dir: Path, offender_risk_path: Path,
                 district_forecasts_path: Path, district_socioeconomic_path: Path, stale_case_days: int):
        self.data_seed_dir = data_seed_dir
        self.offender_risk_path = offender_risk_path
        self.district_forecasts_path = district_forecasts_path
        self.district_socioeconomic_path = district_socioeconomic_path
        self.stale_case_days = stale_case_days

        self.fir: pd.DataFrame | None = None
        self.link: pd.DataFrame | None = None
        self.person: pd.DataFrame | None = None
        self.network_edge: pd.DataFrame | None = None
        self.offender_risk: pd.DataFrame | None = None
        self.district_forecasts: pd.DataFrame | None = None
        self.district_socioeconomic: pd.DataFrame | None = None

        self.case_priority: pd.DataFrame | None = None
        self.district_volume: pd.Series | None = None
        self.max_date = None

    def load(self):
        d = self.data_seed_dir
        self.fir = pd.read_csv(d / "fir.csv", dtype={"fir_id": str}, parse_dates=["date_reported"]).set_index(
            "fir_id", drop=False
        )
        self.link = pd.read_csv(d / "fir_person_link.csv", dtype={"fir_id": str})
        self.person = pd.read_csv(d / "person.csv").set_index("person_id", drop=False)
        self.network_edge = pd.read_csv(d / "network_edge.csv")
        self.offender_risk = pd.read_csv(self.offender_risk_path).set_index("person_id", drop=False)
        self.district_forecasts = pd.read_csv(self.district_forecasts_path)
        self.district_socioeconomic = pd.read_csv(self.district_socioeconomic_path)

        self.max_date = self.fir["date_reported"].max()
        self.district_volume = self.fir.groupby("district").size()
        self.case_priority = self._build_case_priority()
        return self

    # ---- case priority -----------------------------------------------------

    def _build_case_priority(self) -> pd.DataFrame:
        unresolved = self.fir[self.fir["status"].isin(UNRESOLVED_STATUSES)].reset_index(drop=True).copy()

        accused = self.link[self.link["role"] == "ACCUSED"].merge(
            self.offender_risk[["person_id", "risk_tier"]].reset_index(drop=True), on="person_id", how="left"
        )
        accused["risk_tier"] = accused["risk_tier"].fillna("LOW")

        def _case_accused_risk(group: pd.DataFrame) -> pd.Series:
            tiers = group["risk_tier"]
            if (tiers == "HIGH").any():
                return pd.Series({"accused_risk_points": 2, "highest_accused_risk_tier": "HIGH"})
            if (tiers == "MEDIUM").any():
                return pd.Series({"accused_risk_points": 1, "highest_accused_risk_tier": "MEDIUM"})
            return pd.Series({"accused_risk_points": 0, "highest_accused_risk_tier": "LOW"})

        case_risk = accused.groupby("fir_id").apply(_case_accused_risk, include_groups=False)

        district_p75 = self.district_volume.quantile(DISTRICT_HOTSPOT_PERCENTILE)

        unresolved["age_days"] = (self.max_date - unresolved["date_reported"]).dt.days
        unresolved["violent_points"] = unresolved["crime_type_code"].isin(VIOLENT_TYPES).astype(int) * 3
        unresolved["hotspot_points"] = (
            unresolved["district"].map(self.district_volume).fillna(0) >= district_p75
        ).astype(int) * 2
        unresolved["stale_points"] = (unresolved["age_days"] > self.stale_case_days).astype(int) * 1
        unresolved = unresolved.merge(case_risk, left_on="fir_id", right_index=True, how="left")
        unresolved["accused_risk_points"] = unresolved["accused_risk_points"].fillna(0).astype(int)
        unresolved["highest_accused_risk_tier"] = unresolved["highest_accused_risk_tier"].fillna("LOW")

        unresolved["priority_score"] = (
            unresolved["violent_points"] + unresolved["accused_risk_points"]
            + unresolved["hotspot_points"] + unresolved["stale_points"]
        )

        def _tier(score: int) -> str:
            if score >= PRIORITY_TIER_THRESHOLDS["HIGH"]:
                return "HIGH"
            if score >= PRIORITY_TIER_THRESHOLDS["MEDIUM"]:
                return "MEDIUM"
            return "LOW"

        unresolved["priority_tier"] = unresolved["priority_score"].apply(_tier)
        return unresolved.sort_values("priority_score", ascending=False)

    def stats(self) -> dict:
        return {
            "total_cases": len(self.fir),
            "total_unresolved_cases": len(self.case_priority),
            "priority_tier_counts": self.case_priority["priority_tier"].value_counts().to_dict(),
            "priority_tier_thresholds": PRIORITY_TIER_THRESHOLDS,
            "stale_case_days_threshold": self.stale_case_days,
            "stale_unresolved_case_count": int((self.case_priority["stale_points"] > 0).sum()),
            "dataset_reference_date": str(self.max_date.date()),
        }

    def _case_row_to_dict(self, row: pd.Series) -> dict:
        return {
            "fir_id": row["fir_id"],
            "state": row["state"],
            "district": row["district"],
            "crime_type_code": row["crime_type_code"],
            "status": row["status"],
            "date_reported": str(row["date_reported"].date()),
            "age_days": int(row["age_days"]),
            "violent_points": int(row["violent_points"]),
            "accused_risk_points": int(row["accused_risk_points"]),
            "hotspot_points": int(row["hotspot_points"]),
            "stale_points": int(row["stale_points"]),
            "priority_score": int(row["priority_score"]),
            "priority_tier": row["priority_tier"],
            "highest_accused_risk_tier": row["highest_accused_risk_tier"],
        }

    def case_priority_list(self, priority_tier: str | None = None, limit: int = 100) -> dict:
        df = self.case_priority
        if priority_tier:
            df = df[df["priority_tier"] == priority_tier]
        df = df.head(limit)
        return {
            "priority_tier": priority_tier,
            "count": len(df),
            "cases": [self._case_row_to_dict(row) for _, row in df.iterrows()],
        }

    def case_detail(self, fir_id: str) -> dict | None:
        row = self.case_priority[self.case_priority["fir_id"] == fir_id]
        if row.empty:
            return None
        return self._case_row_to_dict(row.iloc[0])

    def case_status_lookup(self, fir_id: str) -> str | None:
        """Raw case status if fir_id exists at all - used to distinguish
        "not found" from "exists but resolved, not in the priority queue"
        for a clearer 404 message."""
        if fir_id not in self.fir.index:
            return None
        return self.fir.loc[fir_id, "status"]

    # ---- person dossier -----------------------------------------------------

    def person_dossier(self, person_id: str) -> dict | None:
        if person_id not in self.person.index:
            return None
        person_row = self.person.loc[person_id]

        offender_risk = None
        if person_id in self.offender_risk.index:
            r = self.offender_risk.loc[person_id]
            offender_risk = {
                "prior_case_count": int(r["prior_case_count"]),
                "distinct_crime_types_count": int(r["distinct_crime_types_count"]),
                "predicted_reoffend_probability_365d": float(r["predicted_reoffend_probability_365d"]),
                "risk_tier": r["risk_tier"],
            }

        edges = self.network_edge[
            (self.network_edge["person_id_a"] == person_id) | (self.network_edge["person_id_b"] == person_id)
        ].copy()
        edges["associate_id"] = edges.apply(
            lambda r: r["person_id_b"] if r["person_id_a"] == person_id else r["person_id_a"], axis=1
        )
        edges = edges.sort_values("shared_fir_count", ascending=False)
        top_associates = [
            {
                "person_id": r["associate_id"],
                "full_name": self.person.loc[r["associate_id"], "full_name"] if r["associate_id"] in self.person.index else None,
                "shared_fir_count": int(r["shared_fir_count"]),
            }
            for _, r in edges.head(10).iterrows()
        ]

        case_links = self.link[self.link["person_id"] == person_id].merge(
            self.fir[["fir_id", "crime_type_code", "date_reported", "status", "district"]].reset_index(drop=True),
            on="fir_id",
        ).sort_values("date_reported", ascending=False)
        cases = [
            {
                "fir_id": r["fir_id"],
                "role": r["role"],
                "crime_type_code": r["crime_type_code"],
                "date_reported": str(r["date_reported"].date()),
                "status": r["status"],
                "district": r["district"],
            }
            for _, r in case_links.iterrows()
        ]

        return {
            "person_id": person_id,
            "full_name": person_row.get("full_name"),
            "gender": person_row.get("gender"),
            "age": None if pd.isna(person_row.get("age")) else int(person_row["age"]),
            "address_district": person_row.get("address_district"),
            "address_state": person_row.get("address_state"),
            "offender_risk": offender_risk,
            "network_degree": len(edges),
            "top_associates": top_associates,
            "cases": cases,
        }

    # ---- district briefing ---------------------------------------------------

    def district_briefing(self, district: str) -> dict | None:
        district_lower = district.lower()
        matches = self.fir[self.fir["district"].str.lower() == district_lower]
        if matches.empty:
            matches = self.fir[self.fir["district"].str.lower().str.contains(district_lower, regex=False)]
        if matches.empty:
            return None
        actual_district = matches.iloc[0]["district"]
        state = matches.iloc[0]["state"]
        rows = self.fir[self.fir["district"] == actual_district]

        total_cases = len(rows)
        unresolved_count = int(rows["status"].isin(UNRESOLVED_STATUSES).sum())
        violent_ratio = float(rows["crime_type_code"].isin(VIOLENT_TYPES).mean())
        property_ratio = float(rows["crime_type_code"].isin(PROPERTY_TYPES).mean())
        percentile_rank = float((self.district_volume <= self.district_volume.get(actual_district, 0)).mean())
        is_hotspot = percentile_rank >= DISTRICT_HOTSPOT_PERCENTILE

        soc_match = self.district_socioeconomic[
            self.district_socioeconomic["fir_district_label"].str.lower() == actual_district.lower()
        ]
        if soc_match.empty:
            socioeconomic = {"available": False}
        else:
            s = soc_match.iloc[0]
            socioeconomic = {
                "available": True,
                "literacy_rate": float(s["literacy_rate"]),
                "urbanization_rate": float(s["urbanization_rate"]),
                "crime_rate_per_100k": float(s["crime_rate_per_100k"]),
            }

        fc_match = self.district_forecasts[
            (self.district_forecasts["district"].str.lower() == actual_district.lower())
            & (self.district_forecasts["series"] == "TOTAL")
        ]
        if fc_match.empty:
            forecast = {"available": False}
        else:
            f = fc_match.iloc[0]
            last_val = float(f["last_observed_value"])
            pct_change = round(float((f["forecast_2015"] - last_val) / last_val * 100), 2) if last_val else None
            forecast = {
                "available": True,
                "last_observed_year": int(f["last_observed_year"]),
                "last_observed_value": last_val,
                "forecast_2015": float(f["forecast_2015"]),
                "pct_change": pct_change,
                "selected_model": f["selected_model"],
            }

        return {
            "state": state,
            "district": actual_district,
            "total_cases": total_cases,
            "unresolved_cases": unresolved_count,
            "violent_ratio": round(violent_ratio, 4),
            "property_ratio": round(property_ratio, 4),
            "case_volume_percentile_rank": round(percentile_rank, 4),
            "is_hotspot": is_hotspot,
            "socioeconomic": socioeconomic,
            "forecast": forecast,
        }


store = AnalyticsStore(
    settings.data_seed_dir, settings.offender_risk_path,
    settings.district_forecasts_path, settings.district_socioeconomic_path, settings.stale_case_days,
)
