"""
Loads the precomputed recidivism risk scores plus the trained model itself
(see scripts/data_generation/offender_profiling/build_recidivism_model.py).
Batch lookups (/risk-accounts, /person/{id}) read the precomputed CSV -
no inference at request time. /predict is the exception: it runs the
actual pickled sklearn model against a hypothetical profile, so a "what if
this person had N priors" query reflects the real trained classifier, not
just a lookup.
"""
import json
import pickle
from pathlib import Path

import pandas as pd

from app.config import settings


class AnalyticsStore:
    def __init__(self, person_scores_path: Path, model_path: Path, feature_metadata_path: Path,
                 eval_stats_path: Path, data_seed_dir: Path):
        self.person_scores_path = person_scores_path
        self.model_path = model_path
        self.feature_metadata_path = feature_metadata_path
        self.eval_stats_path = eval_stats_path
        self.data_seed_dir = data_seed_dir

        self.scores: pd.DataFrame | None = None
        self.model = None
        self.feature_metadata: dict = {}
        self.eval_stats: dict = {}

    def load(self):
        scores = pd.read_csv(self.person_scores_path)
        person = pd.read_csv(self.data_seed_dir / "person.csv")
        self.scores = scores.merge(
            person[["person_id", "full_name", "gender", "age", "address_district", "address_state"]],
            on="person_id", how="left",
        ).set_index("person_id", drop=False)

        with self.model_path.open("rb") as f:
            self.model = pickle.load(f)
        self.feature_metadata = json.loads(self.feature_metadata_path.read_text())
        self.eval_stats = json.loads(self.eval_stats_path.read_text())
        return self

    # ---- model info -----------------------------------------------------

    def model_info(self) -> dict:
        return self.eval_stats

    # ---- lookups ---------------------------------------------------------

    def _row_to_profile(self, row: pd.Series) -> dict:
        return {
            "person_id": row["person_id"],
            "full_name": row.get("full_name"),
            "gender": row.get("gender"),
            "age": None if pd.isna(row.get("age")) else int(row["age"]),
            "address_district": row.get("address_district"),
            "address_state": row.get("address_state"),
            "prior_case_count": int(row["prior_case_count"]),
            "distinct_crime_types_count": int(row["distinct_crime_types_count"]),
            "predicted_reoffend_probability_365d": float(row["predicted_reoffend_probability_365d"]),
            "risk_tier": row["risk_tier"],
        }

    def person_profile(self, person_id: str) -> dict | None:
        if person_id not in self.scores.index:
            return None
        return self._row_to_profile(self.scores.loc[person_id])

    def risk_list(self, risk_tier: str = "HIGH", limit: int = 100) -> dict:
        df = self.scores[self.scores["risk_tier"] == risk_tier]
        df = df.sort_values("predicted_reoffend_probability_365d", ascending=False).head(limit)
        return {
            "risk_tier": risk_tier,
            "count": len(df),
            "persons": [self._row_to_profile(row) for _, row in df.iterrows()],
        }

    # ---- live inference ----------------------------------------------------

    def predict(
        self, prior_case_count: int, distinct_prior_crime_types: int, prior_violent_count: int,
        prior_property_count: int, days_since_first_case: int, current_is_violent: bool,
        current_is_property: bool, gender: str, age: int, state: str,
    ) -> dict:
        state_categories = self.feature_metadata["state_categories"]
        state_bucket = state.upper() if state.upper() in state_categories else "OTHER"

        row = {
            "prior_case_count": prior_case_count,
            "distinct_prior_crime_types": distinct_prior_crime_types,
            "prior_violent_count": prior_violent_count,
            "prior_property_count": prior_property_count,
            "days_since_first_case": days_since_first_case,
            "age": age,
            "current_is_violent": int(current_is_violent),
            "current_is_property": int(current_is_property),
            "gender_M": 1 if gender.upper() == "M" else 0,
        }
        for state_name in state_categories:
            row[f"state_{state_name}"] = 1 if state_name == state_bucket else 0

        X = pd.DataFrame([row])[self.feature_metadata["feature_names"]]
        proba = float(self.model.predict_proba(X)[0, 1])

        thresholds = self.eval_stats["risk_tier_thresholds"]
        if proba >= thresholds["p90_high_cutoff"]:
            tier = "HIGH"
        elif proba >= thresholds["p65_medium_cutoff"]:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        return {
            "predicted_reoffend_probability_365d": round(proba, 4),
            "risk_tier": tier,
            "model_used": self.eval_stats["selected_model"],
            "inputs": {
                "prior_case_count": prior_case_count,
                "distinct_prior_crime_types": distinct_prior_crime_types,
                "prior_violent_count": prior_violent_count,
                "prior_property_count": prior_property_count,
                "days_since_first_case": days_since_first_case,
                "current_is_violent": current_is_violent,
                "current_is_property": current_is_property,
                "gender": gender,
                "age": age,
                "state": state,
            },
        }


store = AnalyticsStore(
    settings.person_scores_path, settings.model_path, settings.feature_metadata_path,
    settings.eval_stats_path, settings.data_seed_dir,
)
