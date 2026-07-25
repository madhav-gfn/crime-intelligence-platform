"""
Offender profiling / recidivism risk (pillar 5). Replaces the rule-based
risk_tier placeholder in data/seed/offender_profile.csv (prior_case_count
thresholds only, since used_weapon_ever is always False under the real
schema - see scripts/data_generation/oltp/README.md) with an actual trained
classifier, evaluated on a genuine held-out test set rather than presented
as-is.

Task definition - and why it's framed this way:
  "Does this person, having just appeared as ACCUSED in a case, appear as
  ACCUSED again within the next 365 days?" A fixed-horizon reoffense window
  (rather than "ever reoffends again") is the standard framing in
  criminology recidivism literature (e.g. 1-year re-arrest rate), and it
  sidesteps a data problem an "ever reoffends" framing would hide: cases
  near the end of the 2020-2024 observation window haven't had time to show
  reoffense even if it would happen in reality. Case appearances without a
  full 365-day follow-up remaining in the dataset are excluded from
  training/evaluation entirely (right-censoring), not labeled 0 by default.

Leakage discipline:
  - Every feature is computed strictly from a person's case history BEFORE
    or AT the case being scored - never from later cases.
  - No network-graph features (co-accused degree/community) are used here,
    even though network-analysis computes them, because the graph is built
    from the FULL dataset and would leak future co-accusal relationships
    into a "prior" feature. Left out on purpose, not an oversight.
  - Train/test split is by PERSON, not by case-appearance - a person's
    multiple appearances never span both sides of the split.
  - occupation/income_bracket are excluded: person.csv only populates them
    for COMPLAINANT-role rows (real-schema gap, see oltp/README.md) - 100%
    missing for every ACCUSED person, confirmed empirically before deciding
    to drop them rather than impute.

Outputs (data/processed/offender-profiling/):
    person_risk_scores.csv   - one row per accused person, scored with the
                                selected trained model using their full
                                history as of their most recent case
    eval_stats.json          - model comparison (vs each other AND vs the
                                existing rule-based baseline), feature
                                importances, censoring/class-balance stats
    model.pkl                - the selected trained sklearn model
    feature_metadata.json    - feature order + state category list, so the
                                service (or a future retrain) can rebuild
                                an identical feature vector

Usage:
    python scripts/data_generation/offender_profiling/build_recidivism_model.py
"""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = ROOT / "data" / "seed"
OUT_DIR = ROOT / "data" / "processed" / "offender-profiling"

FOLLOW_UP_DAYS = 365
RANDOM_SEED = 42
TEST_FRACTION = 0.2
TOP_N_STATES = 12  # one-hot the highest-volume states, bucket the rest as OTHER

# Mirrors backend/services/pattern-analytics/app/taxonomy.py - see that
# module's docstring for why this is a literal copy, not a shared import.
VIOLENT_CODES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY",
    "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY",
}
PROPERTY_CODES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}


def load_accused_appearances() -> pd.DataFrame:
    fir = pd.read_csv(SEED_DIR / "fir.csv", dtype={"fir_id": str}, parse_dates=["date_reported"])
    link = pd.read_csv(SEED_DIR / "fir_person_link.csv", dtype={"fir_id": str})
    person = pd.read_csv(SEED_DIR / "person.csv")

    accused = link[link["role"] == "ACCUSED"].merge(
        fir[["fir_id", "date_reported", "crime_type_code", "state", "district"]], on="fir_id"
    )
    accused = accused.merge(person[["person_id", "gender", "age", "address_state"]], on="person_id")
    accused["is_violent"] = accused["crime_type_code"].isin(VIOLENT_CODES)
    accused["is_property"] = accused["crime_type_code"].isin(PROPERTY_CODES)
    return accused.sort_values(["person_id", "date_reported"]).reset_index(drop=True)


def build_feature_rows(accused: pd.DataFrame, top_states: list[str]) -> pd.DataFrame:
    """One row per case-appearance: prior-history features as of that case."""
    rows = []
    for person_id, group in accused.groupby("person_id"):
        group = group.sort_values("date_reported").reset_index(drop=True)
        first_date = group.loc[0, "date_reported"]
        for i, row in group.iterrows():
            prior = group.iloc[:i]
            state = row["address_state"] if row["address_state"] in top_states else "OTHER"
            rows.append({
                "person_id": person_id,
                "fir_id": row["fir_id"],
                "case_date": row["date_reported"],
                "appearance_index": i,
                "prior_case_count": i,
                "distinct_prior_crime_types": prior["crime_type_code"].nunique(),
                "prior_violent_count": int(prior["is_violent"].sum()),
                "prior_property_count": int(prior["is_property"].sum()),
                "days_since_first_case": (row["date_reported"] - first_date).days,
                "current_is_violent": bool(row["is_violent"]),
                "current_is_property": bool(row["is_property"]),
                "gender": row["gender"],
                "age": row["age"],
                "state": state,
            })
    return pd.DataFrame(rows)


def label_reoffense(accused: pd.DataFrame, feature_rows: pd.DataFrame) -> pd.DataFrame:
    max_date = accused["date_reported"].max()
    cutoff = max_date - pd.Timedelta(days=FOLLOW_UP_DAYS)

    dates_by_person = {pid: g["date_reported"].sort_values().to_numpy() for pid, g in accused.groupby("person_id")}

    def _reoffends_within_window(person_id: str, case_date) -> bool:
        window_end = case_date + pd.Timedelta(days=FOLLOW_UP_DAYS)
        dates = dates_by_person[person_id]
        return bool(((dates > np.datetime64(case_date)) & (dates <= np.datetime64(window_end))).any())

    feature_rows = feature_rows.copy()
    feature_rows["eligible"] = feature_rows["case_date"] <= cutoff
    feature_rows["reoffends_within_365d"] = feature_rows.apply(
        lambda r: _reoffends_within_window(r["person_id"], r["case_date"]), axis=1
    )
    return feature_rows, max_date, cutoff


FEATURE_COLUMNS_NUMERIC = [
    "prior_case_count", "distinct_prior_crime_types", "prior_violent_count", "prior_property_count",
    "days_since_first_case", "age",
]
FEATURE_COLUMNS_BOOL = ["current_is_violent", "current_is_property"]


def vectorize(df: pd.DataFrame, state_categories: list[str]) -> pd.DataFrame:
    X = df[FEATURE_COLUMNS_NUMERIC + FEATURE_COLUMNS_BOOL].copy()
    for col in FEATURE_COLUMNS_BOOL:
        X[col] = X[col].astype(int)
    X["gender_M"] = (df["gender"] == "M").astype(int)
    for state in state_categories:
        X[f"state_{state}"] = (df["state"] == state).astype(int)
    return X


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading accused case appearances...")
    accused = load_accused_appearances()
    top_states = accused["address_state"].value_counts().head(TOP_N_STATES).index.tolist()

    print("Building prior-history feature rows...")
    feature_rows = build_feature_rows(accused, top_states)
    feature_rows, max_date, cutoff = label_reoffense(accused, feature_rows)

    eligible = feature_rows[feature_rows["eligible"]].copy()
    print(f"Total case appearances: {len(feature_rows)}")
    print(f"Eligible for training (>= {FOLLOW_UP_DAYS}d follow-up before {max_date.date()}): {len(eligible)}")
    print(f"Positive rate (reoffends within {FOLLOW_UP_DAYS}d): {eligible['reoffends_within_365d'].mean():.3f}")

    state_categories = top_states + ["OTHER"]
    X_all = vectorize(eligible, state_categories)
    y_all = eligible["reoffends_within_365d"].astype(int)
    feature_names = X_all.columns.tolist()

    rng = np.random.default_rng(RANDOM_SEED)
    unique_persons = eligible["person_id"].unique()
    rng.shuffle(unique_persons)
    n_test = int(len(unique_persons) * TEST_FRACTION)
    test_persons = set(unique_persons[:n_test])

    test_mask = eligible["person_id"].isin(test_persons)
    X_train, y_train = X_all[~test_mask], y_all[~test_mask]
    X_test, y_test = X_all[test_mask], y_all[test_mask]
    print(f"Train: {len(X_train)} appearances ({(~test_mask).sum()}) / Test: {len(X_test)} appearances, "
          f"split by {len(unique_persons)} unique persons ({len(test_persons)} held out)")

    print("Training models...")
    models = {
        "LOGISTIC_REGRESSION": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_SEED),
        "RANDOM_FOREST": RandomForestClassifier(
            n_estimators=200, max_depth=6, class_weight="balanced", random_state=RANDOM_SEED
        ),
    }

    def _evaluate(y_true, y_pred, y_proba) -> dict:
        return {
            "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        }

    results = {}
    fitted = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        results[name] = _evaluate(y_test, pred, proba)
        fitted[name] = model

    # Baseline: the existing rule-based signal, boiled down to what's still
    # meaningful under the real schema (used_weapon_ever is always False -
    # see oltp/README.md - so the only live signal left is prior_case_count).
    baseline_pred = (X_test["prior_case_count"] >= 1).astype(int)
    results["BASELINE_PRIOR_CASE_RULE"] = {
        "precision": round(float(precision_score(y_test, baseline_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, baseline_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, baseline_pred, zero_division=0)), 4),
        "roc_auc": None,  # binary rule, no probability to score AUC against
    }

    selected_model_name = max(("LOGISTIC_REGRESSION", "RANDOM_FOREST"), key=lambda n: results[n]["roc_auc"])
    selected_model = fitted[selected_model_name]
    print(f"Model comparison: {results}")
    print(f"Selected model: {selected_model_name}")

    if selected_model_name == "RANDOM_FOREST":
        importances = dict(zip(feature_names, [round(float(v), 4) for v in selected_model.feature_importances_]))
    else:
        importances = dict(zip(feature_names, [round(float(v), 4) for v in selected_model.coef_[0]]))
    importances = dict(sorted(importances.items(), key=lambda kv: -abs(kv[1])))

    # Score every accused person's CURRENT profile (their full history as of
    # their most recent case) - this is what the service actually serves.
    latest_per_person = feature_rows.sort_values("appearance_index").groupby("person_id").tail(1)
    X_current = vectorize(latest_per_person, state_categories)
    current_proba = selected_model.predict_proba(X_current)[:, 1]
    person_scores = pd.DataFrame({
        "person_id": latest_per_person["person_id"].values,
        "prior_case_count": latest_per_person["prior_case_count"].values + 1,  # +1 to count the case itself
        "distinct_crime_types_count": latest_per_person["distinct_prior_crime_types"].values,
        "predicted_reoffend_probability_365d": np.round(current_proba, 4),
    })
    # Fixed 0/0.33/0.66 probability bins don't fit this model's actual output
    # range (predicted probabilities cluster tightly, e.g. ~0.29-0.81 in the
    # current build) - almost everyone would land in one bin. Percentile
    # thresholds derived from the real score distribution instead, same
    # rationale as the P99 fan-out/fan-in thresholds in financial-crime-analysis.
    p65, p90 = person_scores["predicted_reoffend_probability_365d"].quantile([0.65, 0.90])
    person_scores["risk_tier"] = np.select(
        [person_scores["predicted_reoffend_probability_365d"] >= p90,
         person_scores["predicted_reoffend_probability_365d"] >= p65],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )
    risk_tier_thresholds = {"p65_medium_cutoff": round(float(p65), 4), "p90_high_cutoff": round(float(p90), 4)}

    person_scores.to_csv(OUT_DIR / "person_risk_scores.csv", index=False)
    with (OUT_DIR / "model.pkl").open("wb") as f:
        pickle.dump(selected_model, f)

    (OUT_DIR / "feature_metadata.json").write_text(json.dumps({
        "feature_names": feature_names,
        "state_categories": state_categories,
        "numeric_features": FEATURE_COLUMNS_NUMERIC,
        "bool_features": FEATURE_COLUMNS_BOOL,
    }, indent=2))

    eval_stats = {
        "follow_up_days": FOLLOW_UP_DAYS,
        "dataset_max_date": str(max_date.date()),
        "eligibility_cutoff_date": str(cutoff.date()),
        "total_case_appearances": len(feature_rows),
        "eligible_case_appearances": len(eligible),
        "censored_case_appearances": len(feature_rows) - len(eligible),
        "positive_rate": round(float(eligible["reoffends_within_365d"].mean()), 4),
        "train_appearances": int((~test_mask).sum()),
        "test_appearances": int(test_mask.sum()),
        "train_persons": len(unique_persons) - len(test_persons),
        "test_persons": len(test_persons),
        "model_comparison": results,
        "selected_model": selected_model_name,
        "feature_importances": importances,
        "total_accused_persons_scored": len(person_scores),
        "risk_tier_thresholds": risk_tier_thresholds,
        "risk_tier_counts": person_scores["risk_tier"].value_counts().to_dict(),
    }
    (OUT_DIR / "eval_stats.json").write_text(json.dumps(eval_stats, indent=2))

    print(f"\nScored {len(person_scores)} accused persons")
    print(f"Risk tiers: {eval_stats['risk_tier_counts']}")
    print(f"Wrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
