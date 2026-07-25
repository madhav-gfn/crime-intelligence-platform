"""
Explainable AI (pillar 9). Loads the precomputed SHAP explanations built by
scripts/data_generation/explainability/build_shap_explanations.py (real,
exact SHAP values via shap.TreeExplainer over offender-profiling's Random
Forest recidivism model - the platform's one actual black-box model) plus
offender-profiling's own model.pkl for /predict-explain, which runs SHAP
live against a hypothetical profile rather than a precomputed lookup, the
same "lookup vs live inference" split offender-profiling's own /predict
endpoint makes.

Six of the seven analytics services are transparent by construction (rule
thresholds, backtested model selection, percentile calibration) - see
methodology() below for what each one actually does. This module doesn't
re-derive that; it reports it, sourced from what those services'
docstrings/READMEs already establish as true.
"""
import json
import pickle
from pathlib import Path

import pandas as pd
import shap

from app.config import settings

METHODOLOGY = [
    {
        "service": "network-analysis",
        "approach": "Graph algorithms (degree/betweenness centrality, Louvain community detection) over the co-accused graph.",
        "transparency_mechanism": "Every metric (degree, community ID, centrality score) is a direct graph-theoretic computation, not a learned model - inherently inspectable.",
    },
    {
        "service": "pattern-analytics",
        "approach": "DBSCAN spatial hotspot clustering; PCA + KMeans severity tiers.",
        "transparency_mechanism": "Cluster assignment and severity tier are reported alongside the actual distance/component values that produced them - unsupervised, no labels to overfit to.",
    },
    {
        "service": "sociological-insights",
        "approach": "Real Census 2011 socioeconomic indicators correlated against real crime-report volumes at district level.",
        "transparency_mechanism": "Plain Pearson correlation coefficients on real joined data; SC/ST share and religion composition deliberately excluded from ranking/correlation endpoints (ecological-fallacy avoidance), not just from this explainability layer.",
    },
    {
        "service": "financial-crime-analysis",
        "approach": "Five rule-based AML flags (fan-out/fan-in degree at P99, rapid passthrough, cross-currency, high-value at P98) combined into a risk_score.",
        "transparency_mechanism": "Every flag that fired for an account is a visible boolean field on the response, not folded into an opaque score - and the rule engine's precision/recall is reported against real ground-truth labels, including its real limitations.",
    },
    {
        "service": "crime-forecasting",
        "approach": "Three transparent time-series models (naive, moving-average, linear-trend), backtested per-series and selected by lowest MAE.",
        "transparency_mechanism": "The backtested MAE for every candidate model is reported alongside the forecast, including the honest finding that the naive baseline often wins - selection isn't hidden or asserted.",
    },
    {
        "service": "offender-profiling",
        "approach": "A trained Random Forest classifier (selected over Logistic Regression by backtested ROC-AUC) predicting 365-day reoffense probability.",
        "transparency_mechanism": (
            "This is the one actual black-box model in the platform - a Random Forest's decision "
            "logic isn't reducible to a simple formula the way the other six services' are. That's "
            "exactly why this service (explainable-ai) exists: real per-person SHAP explanations, "
            "not just a global feature_importances_ list."
        ),
    },
    {
        "service": "investigator-decision-support",
        "approach": "A transparent point-based case-priority score (violent +3, accused risk +1/+2, district hotspot +2, stale +1).",
        "transparency_mechanism": "Every component of the score is returned as its own field alongside the total - the breakdown IS the explanation, no separate explainability layer needed.",
    },
]


class AnalyticsStore:
    def __init__(
        self, shap_values_path: Path, global_importance_path: Path, model_path: Path,
        feature_metadata_path: Path, person_scores_path: Path, person_feature_vectors_path: Path,
        offender_eval_stats_path: Path, data_seed_dir: Path,
    ):
        self.shap_values_path = shap_values_path
        self.global_importance_path = global_importance_path
        self.model_path = model_path
        self.feature_metadata_path = feature_metadata_path
        self.person_scores_path = person_scores_path
        self.person_feature_vectors_path = person_feature_vectors_path
        self.offender_eval_stats_path = offender_eval_stats_path
        self.data_seed_dir = data_seed_dir

        self.shap_values: pd.DataFrame | None = None
        self.feature_vectors: pd.DataFrame | None = None
        self.global_importance: dict = {}
        self.model = None
        self.explainer = None
        self.feature_metadata: dict = {}
        self.offender_eval_stats: dict = {}
        self.person_scores: pd.DataFrame | None = None
        self.feature_names: list[str] = []

    def load(self):
        shap_values = pd.read_csv(self.shap_values_path)
        person = pd.read_csv(self.data_seed_dir / "person.csv")
        self.shap_values = shap_values.merge(
            person[["person_id", "full_name"]], on="person_id", how="left",
        ).set_index("person_id", drop=False)

        self.feature_vectors = pd.read_csv(self.person_feature_vectors_path).set_index("person_id", drop=False)

        self.global_importance = json.loads(self.global_importance_path.read_text())
        self.feature_metadata = json.loads(self.feature_metadata_path.read_text())
        self.offender_eval_stats = json.loads(self.offender_eval_stats_path.read_text())
        self.feature_names = self.feature_metadata["feature_names"]

        scores = pd.read_csv(self.person_scores_path)
        self.person_scores = scores.set_index("person_id", drop=False)

        with self.model_path.open("rb") as f:
            self.model = pickle.load(f)
        self.explainer = shap.TreeExplainer(self.model)
        return self

    # ---- methodology / model-wide ----------------------------------------

    def methodology(self) -> dict:
        return {
            "summary": (
                "Six of the seven analytics services are transparent by construction (visible "
                "thresholds, backtested selection, percentile calibration). Offender-profiling's "
                "Random Forest is the one actual black-box model - this service adds real, "
                "validated SHAP explanations specifically for it."
            ),
            "pillars": METHODOLOGY,
        }

    def model_info(self) -> dict:
        return self.global_importance

    # ---- per-person (precomputed) ----------------------------------------

    def _row_to_contributions(self, shap_row: pd.Series, feature_row: pd.Series) -> list[dict]:
        contributions = [
            {
                "feature": name,
                "feature_value": float(feature_row[name]),
                "shap_value": float(shap_row[f"shap_{name}"]),
            }
            for name in self.feature_names
        ]
        return sorted(contributions, key=lambda c: -abs(c["shap_value"]))

    def person_explanation(self, person_id: str) -> dict | None:
        if person_id not in self.shap_values.index:
            return None
        row = self.shap_values.loc[person_id]
        feature_row = self.feature_vectors.loc[person_id]
        score_row = self.person_scores.loc[person_id]
        all_contributions = self._row_to_contributions(row, feature_row)
        return {
            "person_id": person_id,
            "full_name": row.get("full_name"),
            "risk_tier": score_row["risk_tier"],
            "predicted_reoffend_probability_365d": float(score_row["predicted_reoffend_probability_365d"]),
            "base_value": float(row["base_value"]),
            "reconstruction_error": float(row["reconstruction_error"]),
            "top_drivers": all_contributions[:5],
            "all_contributions": all_contributions,
        }

    # ---- live inference (mirrors offender-profiling's /predict) ---------

    def predict_explain(
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

        X = pd.DataFrame([row])[self.feature_names]
        proba = float(self.model.predict_proba(X)[0, 1])

        raw = self.explainer.shap_values(X)
        shap_for_class1 = raw[0, :, 1]
        base_value = float(self.explainer.expected_value[1])

        thresholds = self.offender_eval_stats["risk_tier_thresholds"]
        if proba >= thresholds["p90_high_cutoff"]:
            tier = "HIGH"
        elif proba >= thresholds["p65_medium_cutoff"]:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        contributions = sorted(
            (
                {"feature": name, "feature_value": float(X.iloc[0][name]), "shap_value": float(shap_for_class1[i])}
                for i, name in enumerate(self.feature_names)
            ),
            key=lambda c: -abs(c["shap_value"]),
        )

        return {
            "predicted_reoffend_probability_365d": round(proba, 4),
            "risk_tier": tier,
            "base_value": round(base_value, 6),
            "top_drivers": contributions[:5],
            "all_contributions": contributions,
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
    settings.shap_values_path, settings.global_importance_path, settings.model_path,
    settings.feature_metadata_path, settings.person_scores_path, settings.person_feature_vectors_path,
    settings.offender_eval_stats_path, settings.data_seed_dir,
)
