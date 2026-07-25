"""
Explainable AI / transparent analytics (pillar 9).

Six of the seven analytics services in this platform are transparent by
construction: rule-based point scores (investigator-decision-support),
visible thresholds (financial-crime-analysis's P99 fan-out/fan-in rules),
backtested model selection (crime-forecasting), and percentile-calibrated
cutoffs (offender-profiling's own risk tiers) all show their reasoning as
plain arithmetic. There's exactly one place in this platform where a
prediction comes out of an actual black-box model: offender-profiling's
Random Forest recidivism classifier. That's the one place post-hoc
explanation actually earns its keep, and it's what the research doc behind
this project calls out by name (SHAP for predictive risk-scoring models).

This script computes real SHAP values - not approximated, not sampled -
using shap.TreeExplainer, which is exact for tree ensembles (it walks the
actual trees rather than perturbing inputs). It runs against
person_feature_vectors.csv, the literal feature matrix
build_recidivism_model.py used to produce person_risk_scores.csv - not a
second, independently-reconstructed feature matrix that could silently
drift from what was actually predicted.

Validation performed, not assumed:
  - Every person's SHAP values are checked to reconstruct their actual
    predicted probability (expected_value + sum(shap_values) == predict_proba)
    to within floating-point tolerance. If they didn't, the explanations
    would be lying about what drove the model - this is not a
    corner-cutting we're willing to make in a criminal-justice-adjacent
    system.
  - Global SHAP importance (mean |SHAP| across all persons) is compared
    against the Random Forest's own built-in feature_importances_ (already
    reported in offender-profiling's eval_stats.json) via Spearman rank
    correlation - they're computed completely differently (impurity
    decrease vs. game-theoretic attribution) and needn't agree, so a
    genuine measured concordance is worth reporting instead of asserting.

Outputs (data/processed/explainability/):
    shap_values.csv       - one row per person, one column per feature
                             (that person's SHAP contribution to their own
                             predicted reoffend probability), plus
                             base_value and reconstruction_error
    global_importance.json - mean |SHAP| per feature (ranked) + Spearman
                             concordance against the RF's built-in
                             feature_importances_

Usage:
    python scripts/data_generation/explainability/build_shap_explanations.py
"""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
OFFENDER_DIR = ROOT / "data" / "processed" / "offender-profiling"
OUT_DIR = ROOT / "data" / "processed" / "explainability"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading offender-profiling's trained model + feature vectors...")
    with (OFFENDER_DIR / "model.pkl").open("rb") as f:
        model = pickle.load(f)
    feature_metadata = json.loads((OFFENDER_DIR / "feature_metadata.json").read_text())
    eval_stats = json.loads((OFFENDER_DIR / "eval_stats.json").read_text())
    feature_vectors = pd.read_csv(OFFENDER_DIR / "person_feature_vectors.csv")
    person_scores = pd.read_csv(OFFENDER_DIR / "person_risk_scores.csv")

    feature_names = feature_metadata["feature_names"]
    person_ids = feature_vectors["person_id"].values
    X = feature_vectors[feature_names]

    print(f"Computing exact SHAP values for {len(X)} persons via TreeExplainer...")
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X)
    # shap>=0.45 returns shape (n_samples, n_features, n_classes) for sklearn
    # classifiers; we only care about class 1 (reoffends).
    shap_for_class1 = raw[:, :, 1]
    base_value = float(np.asarray(explainer.expected_value)[1])

    print("Validating reconstruction against the model's actual predicted probabilities...")
    actual_proba = model.predict_proba(X)[:, 1]
    reconstructed = base_value + shap_for_class1.sum(axis=1)
    reconstruction_error = np.abs(reconstructed - actual_proba)
    max_error = float(reconstruction_error.max())
    print(f"Max reconstruction error across {len(X)} persons: {max_error:.2e}")
    if max_error > 1e-6:
        raise RuntimeError(
            f"SHAP reconstruction error {max_error:.2e} exceeds tolerance - "
            "explanations would not faithfully reflect the model's actual predictions."
        )

    shap_df = pd.DataFrame(shap_for_class1, columns=[f"shap_{c}" for c in feature_names])
    shap_df.insert(0, "person_id", person_ids)
    shap_df["base_value"] = round(base_value, 6)
    shap_df["reconstructed_probability"] = np.round(reconstructed, 6)
    shap_df["actual_predicted_probability"] = person_scores.set_index("person_id").loc[
        person_ids, "predicted_reoffend_probability_365d"
    ].values
    shap_df["reconstruction_error"] = reconstruction_error
    shap_df.to_csv(OUT_DIR / "shap_values.csv", index=False)

    print("Computing global SHAP importance and comparing against the RF's built-in importances...")
    mean_abs_shap = {name: float(np.abs(shap_for_class1[:, i]).mean()) for i, name in enumerate(feature_names)}
    mean_abs_shap = dict(sorted(mean_abs_shap.items(), key=lambda kv: -kv[1]))

    rf_importance = eval_stats["feature_importances"]
    common_features = [f for f in feature_names if f in rf_importance]
    shap_rank = {f: r for r, f in enumerate(mean_abs_shap.keys())}
    rf_rank = {f: r for r, f in enumerate(sorted(rf_importance, key=lambda k: -abs(rf_importance[k])))}
    corr, _ = spearmanr([shap_rank[f] for f in common_features], [rf_rank[f] for f in common_features])

    global_importance = {
        "method": "mean(|SHAP value|) across all scored persons, class=reoffends_within_365d",
        "base_value": round(base_value, 6),
        "mean_abs_shap_by_feature": {k: round(v, 6) for k, v in mean_abs_shap.items()},
        "top_5_drivers": list(mean_abs_shap.keys())[:5],
        "concordance_with_rf_builtin_importance": {
            "metric": "spearman_rank_correlation",
            "value": round(float(corr), 4),
            "note": (
                "SHAP importance (game-theoretic attribution of actual predictions) and "
                "scikit-learn's feature_importances_ (mean impurity decrease during training) "
                "are computed from entirely different definitions of 'important' - they need not "
                "agree. A strong positive correlation here is corroborating evidence the model "
                "isn't leaning on some feature training-time impurity overweights but which barely "
                "moves real predictions, not a redundant recomputation of the same number."
            ),
        },
        "total_persons_explained": len(X),
        "max_reconstruction_error": max_error,
    }
    (OUT_DIR / "global_importance.json").write_text(json.dumps(global_importance, indent=2))

    print(f"\nTop 5 SHAP drivers: {global_importance['top_5_drivers']}")
    print(f"Spearman concordance with RF built-in importance: {corr:.4f}")
    print(f"Wrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
