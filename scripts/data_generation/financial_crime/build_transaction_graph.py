"""
Builds account-level risk features and a bounded transaction graph from the
real IBM AML benchmark dataset (data/raw/aml-ibm/, HI-Small variant -
5,078,345 transactions, 518,581 accounts, CDLA-Sharing-1.0 license - see
data/raw/MANIFEST.md). Unlike the other three services, this pillar runs
entirely on real (if synthetically-generated-for-benchmarking) transaction
data with real ground-truth labels (Is Laundering), not NCRB-calibrated
synthetic FIRs.

Rule thresholds (fan-out/fan-in degree, high-value transaction) are computed
as percentiles of the actual dataset rather than hardcoded guesses, and the
resulting values are written to eval_stats.json alongside a precision/
recall/F1 evaluation of the rule engine against the ground-truth labels -
this is the one pillar where "does the analytics actually work" can be
answered with a real number instead of a plausibility argument.

Outputs (data/processed/financial-crime/):
    account_features.csv     - one row per account (~518k), risk flags + tier
    suspicious_edges.csv     - bounded edge list (HIGH-risk endpoint or
                                ground-truth-laundering edge only) for graph/
                                path queries - NOT the full ~3M-edge graph,
                                see README for why
    laundering_patterns.json - the 370 hand-labeled typology examples in
                                HI-Small_Patterns.txt, parsed into structured
                                form (FAN-OUT, CYCLE, FAN-IN, GATHER-SCATTER,
                                SCATTER-GATHER, STACK, BIPARTITE, RANDOM)
    eval_stats.json           - dataset totals, the actual threshold values
                                used, and rule-engine precision/recall/F1
                                against ground truth at two flagging levels

Usage:
    python scripts/data_generation/financial_crime/build_transaction_graph.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
TRANS_PATH = ROOT / "data" / "raw" / "aml-ibm" / "HI-Small_Trans.csv"
ACCOUNTS_PATH = ROOT / "data" / "raw" / "aml-ibm" / "HI-Small_accounts.csv"
PATTERNS_PATH = ROOT / "data" / "raw" / "aml-ibm" / "HI-Small_Patterns.txt"
OUT_DIR = ROOT / "data" / "processed" / "financial-crime"

# Percentile cutoffs for the degree/value rules - see README for rationale
# (chosen so each rule alone flags roughly the top 1-2% of accounts/txns,
# not an arbitrary round number).
FAN_DEGREE_PERCENTILE = 0.99
HIGH_VALUE_PERCENTILE = 0.98
PASSTHROUGH_MIN_TXNS = 3
PASSTHROUGH_RATIO_BAND = (0.85, 1.15)
MAX_SUSPICIOUS_EDGES = 20_000


def load_transactions() -> pd.DataFrame:
    df = pd.read_csv(
        TRANS_PATH,
        dtype={
            "From Bank": "int32", "Account": "category", "To Bank": "int32", "Account.1": "category",
            "Amount Received": "float32", "Receiving Currency": "category",
            "Amount Paid": "float32", "Payment Currency": "category",
            "Payment Format": "category", "Is Laundering": "int8",
        },
    )
    df = df.rename(columns={"Account": "from_id", "Account.1": "to_id"})
    return df


def load_accounts() -> pd.DataFrame:
    df = pd.read_csv(ACCOUNTS_PATH)
    # 16 of 518,581 account numbers collide across two different banks in
    # the source data (out of scope to disambiguate for a demo) - keep the
    # first occurrence, documented rather than silently overwritten.
    df = df.drop_duplicates(subset="Account Number", keep="first")
    return df.set_index("Account Number")


def build_account_features(df: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    out_agg = df.groupby("from_id", observed=True).agg(
        out_amount=("Amount Paid", "sum"),
        out_count=("Amount Paid", "size"),
        out_degree=("to_id", "nunique"),
        max_out_txn=("Amount Paid", "max"),
        out_laundering_count=("Is Laundering", "sum"),
    )
    in_agg = df.groupby("to_id", observed=True).agg(
        in_amount=("Amount Received", "sum"),
        in_count=("Amount Received", "size"),
        in_degree=("from_id", "nunique"),
        max_in_txn=("Amount Received", "max"),
        in_laundering_count=("Is Laundering", "sum"),
    )
    out_currencies = df.groupby("from_id", observed=True)["Payment Currency"].agg(lambda s: frozenset(s))
    in_currencies = df.groupby("to_id", observed=True)["Receiving Currency"].agg(lambda s: frozenset(s))

    features = pd.concat([out_agg, in_agg], axis=1).fillna(0.0)
    features["out_degree"] = features["out_degree"].astype(int)
    features["in_degree"] = features["in_degree"].astype(int)
    features["out_count"] = features["out_count"].astype(int)
    features["in_count"] = features["in_count"].astype(int)
    features["out_laundering_count"] = features["out_laundering_count"].astype(int)
    features["in_laundering_count"] = features["in_laundering_count"].astype(int)

    def _as_set(v) -> frozenset:
        return v if isinstance(v, frozenset) else frozenset()

    all_currencies = out_currencies.combine(
        in_currencies, lambda a, b: _as_set(a) | _as_set(b), fill_value=frozenset()
    )
    all_currencies = all_currencies.reindex(features.index)
    features["distinct_currencies"] = all_currencies.apply(lambda s: len(s) if isinstance(s, frozenset) else 0)

    features["max_single_txn"] = features[["max_out_txn", "max_in_txn"]].max(axis=1)
    features["laundering_txn_count"] = features["out_laundering_count"] + features["in_laundering_count"]
    features["ground_truth_laundering"] = features["laundering_txn_count"] > 0

    features = features.join(accounts[["Bank Name", "Entity ID", "Entity Name"]], how="left")
    features.index.name = "account_id"
    features = features.reset_index()
    return features


def apply_rules(features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    fan_out_threshold = float(features.loc[features["out_degree"] > 0, "out_degree"].quantile(FAN_DEGREE_PERCENTILE))
    fan_in_threshold = float(features.loc[features["in_degree"] > 0, "in_degree"].quantile(FAN_DEGREE_PERCENTILE))
    all_amounts = pd.concat([features["max_out_txn"], features["max_in_txn"]])
    high_value_threshold = float(all_amounts[all_amounts > 0].quantile(HIGH_VALUE_PERCENTILE))

    features["flag_high_fan_out"] = features["out_degree"] >= fan_out_threshold
    features["flag_high_fan_in"] = features["in_degree"] >= fan_in_threshold

    ratio = features["out_amount"] / features["in_amount"].replace(0, np.nan)
    lo, hi = PASSTHROUGH_RATIO_BAND
    features["flag_rapid_passthrough"] = (
        (features["in_count"] >= PASSTHROUGH_MIN_TXNS)
        & (features["out_count"] >= PASSTHROUGH_MIN_TXNS)
        & ratio.between(lo, hi)
    ).fillna(False)

    features["flag_cross_currency"] = features["distinct_currencies"] >= 2
    features["flag_high_value_txn"] = features["max_single_txn"] >= high_value_threshold

    flag_cols = [
        "flag_high_fan_out", "flag_high_fan_in", "flag_rapid_passthrough",
        "flag_cross_currency", "flag_high_value_txn",
    ]
    features["risk_score"] = features[flag_cols].sum(axis=1)
    features["risk_tier"] = np.select(
        [features["risk_score"] >= 3, features["risk_score"] == 2],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    thresholds = {
        "fan_out_degree_p99": round(fan_out_threshold, 2),
        "fan_in_degree_p99": round(fan_in_threshold, 2),
        "high_value_txn_p98": round(high_value_threshold, 2),
        "passthrough_min_txns": PASSTHROUGH_MIN_TXNS,
        "passthrough_ratio_band": list(PASSTHROUGH_RATIO_BAND),
    }
    return features, thresholds


def evaluate(features: pd.DataFrame) -> dict:
    truth = features["ground_truth_laundering"]

    def _prf(flagged: pd.Series) -> dict:
        tp = int((flagged & truth).sum())
        fp = int((flagged & ~truth).sum())
        fn = int((~flagged & truth).sum())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return {
            "flagged_accounts": int(flagged.sum()),
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        }

    return {
        "ground_truth_laundering_accounts": int(truth.sum()),
        "total_accounts": len(features),
        "high_only": _prf(features["risk_tier"] == "HIGH"),
        "medium_or_high": _prf(features["risk_tier"].isin(["MEDIUM", "HIGH"])),
    }


def build_suspicious_edges(df: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    high_risk_ids = set(features.loc[features["risk_tier"] == "HIGH", "account_id"])

    edges = df.groupby(["from_id", "to_id"], observed=True).agg(
        shared_txn_count=("Amount Paid", "size"),
        total_amount_paid=("Amount Paid", "sum"),
        laundering_txn_count=("Is Laundering", "sum"),
    ).reset_index()

    is_suspicious = (
        edges["from_id"].astype(str).isin(high_risk_ids)
        | edges["to_id"].astype(str).isin(high_risk_ids)
        | (edges["laundering_txn_count"] > 0)
    )
    edges = edges[is_suspicious].sort_values(
        ["laundering_txn_count", "total_amount_paid"], ascending=[False, False]
    )
    return edges.head(MAX_SUSPICIOUS_EDGES)


def parse_patterns(path: Path) -> list[dict]:
    patterns = []
    current = None
    pattern_id = 0
    header_re = re.compile(r"^BEGIN LAUNDERING ATTEMPT\s*-\s*(.+)$")

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = header_re.match(line)
        if m:
            pattern_id += 1
            typology, _, descriptor = m.group(1).partition(":")
            current = {
                "pattern_id": f"PAT-{pattern_id:04d}",
                "typology": typology.strip(),
                "descriptor": descriptor.strip(),
                "transactions": [],
            }
            continue
        if line.startswith("END LAUNDERING ATTEMPT"):
            if current is not None:
                accounts = set()
                for t in current["transactions"]:
                    accounts.add(t["from_account"])
                    accounts.add(t["to_account"])
                current["accounts_involved"] = sorted(accounts)
                current["n_transactions"] = len(current["transactions"])
                patterns.append(current)
            current = None
            continue
        if current is not None:
            parts = line.split(",")
            if len(parts) == 11:
                current["transactions"].append({
                    "timestamp": parts[0], "from_bank": parts[1], "from_account": parts[2],
                    "to_bank": parts[3], "to_account": parts[4],
                    "amount_received": float(parts[5]), "receiving_currency": parts[6],
                    "amount_paid": float(parts[7]), "payment_currency": parts[8],
                    "payment_format": parts[9], "is_laundering": int(parts[10]),
                })
    return patterns


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading transactions...")
    df = load_transactions()
    print(f"  {len(df):,} transactions, {df['Is Laundering'].sum():,} labeled laundering")

    print("Loading accounts...")
    accounts = load_accounts()

    print("Building account features...")
    features = build_account_features(df, accounts)
    features, thresholds = apply_rules(features)
    print(f"  {len(features):,} accounts scored")
    print(f"  risk tiers: {features['risk_tier'].value_counts().to_dict()}")

    print("Evaluating rule engine against ground truth...")
    eval_stats = evaluate(features)
    eval_stats["thresholds"] = thresholds
    eval_stats["total_transactions"] = int(len(df))
    eval_stats["ground_truth_laundering_transactions"] = int(df["Is Laundering"].sum())
    print(f"  HIGH-only: {eval_stats['high_only']}")
    print(f"  MEDIUM+HIGH: {eval_stats['medium_or_high']}")

    print("Building suspicious edge list...")
    edges = build_suspicious_edges(df, features)
    print(f"  {len(edges):,} edges (capped at {MAX_SUSPICIOUS_EDGES:,})")

    print("Parsing labeled laundering patterns...")
    patterns = parse_patterns(PATTERNS_PATH)
    print(f"  {len(patterns)} labeled pattern instances")

    features_out = features.drop(columns=["max_out_txn", "max_in_txn"])
    features_out.to_csv(OUT_DIR / "account_features.csv", index=False)
    edges.to_csv(OUT_DIR / "suspicious_edges.csv", index=False)
    (OUT_DIR / "laundering_patterns.json").write_text(json.dumps(patterns, indent=2))
    (OUT_DIR / "eval_stats.json").write_text(json.dumps(eval_stats, indent=2))

    print(f"\nWrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
