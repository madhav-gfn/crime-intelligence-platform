"""
Loads the precomputed account risk features, bounded suspicious-edge graph,
labeled laundering-pattern library, and rule-engine evaluation stats built
by scripts/data_generation/financial_crime/build_transaction_graph.py from
the real IBM AML benchmark dataset (data/raw/aml-ibm/, HI-Small variant).

account_features.csv covers all ~515k accounts that appear in at least one
transaction (full coverage, not a sample) - risk_tier is computed for every
account. suspicious_edges.csv is deliberately NOT the full ~3M-edge
transaction graph - it's capped to edges touching a HIGH-risk account or
carrying a ground-truth-laundering-labeled transaction (~20k edges), which
keeps /path and /graph queries fast and demo-navigable. See README for why
that's a legitimate scoping choice, not a hidden data loss.
"""
import json
from pathlib import Path

import networkx as nx
import pandas as pd

from app.config import settings


def _clean(value):
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


class AnalyticsStore:
    def __init__(self, account_features_path: Path, suspicious_edges_path: Path,
                 patterns_path: Path, eval_stats_path: Path):
        self.account_features_path = account_features_path
        self.suspicious_edges_path = suspicious_edges_path
        self.patterns_path = patterns_path
        self.eval_stats_path = eval_stats_path

        self.accounts: pd.DataFrame | None = None
        self.edges: pd.DataFrame | None = None
        self.patterns: list[dict] = []
        self.eval_stats: dict = {}
        self.graph = nx.DiGraph()

    def load(self):
        self.accounts = pd.read_csv(self.account_features_path, dtype={"account_id": str}).set_index(
            "account_id", drop=False
        )
        self.edges = pd.read_csv(
            self.suspicious_edges_path, dtype={"from_id": str, "to_id": str}
        )
        self.patterns = json.loads(self.patterns_path.read_text())
        self.eval_stats = json.loads(self.eval_stats_path.read_text())

        self.graph = nx.DiGraph()
        for row in self.edges.itertuples():
            self.graph.add_edge(
                row.from_id, row.to_id,
                shared_txn_count=int(row.shared_txn_count),
                total_amount_paid=float(row.total_amount_paid),
                laundering_txn_count=int(row.laundering_txn_count),
            )
        return self

    # ---- stats ---------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_accounts": len(self.accounts),
            "total_transactions": self.eval_stats.get("total_transactions", 0),
            "ground_truth_laundering_accounts": self.eval_stats.get("ground_truth_laundering_accounts", 0),
            "ground_truth_laundering_transactions": self.eval_stats.get("ground_truth_laundering_transactions", 0),
            "risk_tier_counts": self.accounts["risk_tier"].value_counts().to_dict(),
            "thresholds": self.eval_stats.get("thresholds", {}),
        }

    # ---- accounts --------------------------------------------------------

    def _row_to_profile(self, row: pd.Series) -> dict:
        return {
            "account_id": row["account_id"],
            "bank_name": _clean(row["Bank Name"]),
            "entity_id": _clean(row["Entity ID"]),
            "entity_name": _clean(row["Entity Name"]),
            "out_amount": float(row["out_amount"]),
            "out_count": int(row["out_count"]),
            "out_degree": int(row["out_degree"]),
            "in_amount": float(row["in_amount"]),
            "in_count": int(row["in_count"]),
            "in_degree": int(row["in_degree"]),
            "distinct_currencies": int(row["distinct_currencies"]),
            "max_single_txn": float(row["max_single_txn"]),
            "laundering_txn_count": int(row["laundering_txn_count"]),
            "ground_truth_laundering": bool(row["ground_truth_laundering"]),
            "flag_high_fan_out": bool(row["flag_high_fan_out"]),
            "flag_high_fan_in": bool(row["flag_high_fan_in"]),
            "flag_rapid_passthrough": bool(row["flag_rapid_passthrough"]),
            "flag_cross_currency": bool(row["flag_cross_currency"]),
            "flag_high_value_txn": bool(row["flag_high_value_txn"]),
            "risk_score": int(row["risk_score"]),
            "risk_tier": row["risk_tier"],
        }

    def account_profile(self, account_id: str) -> dict | None:
        if account_id not in self.accounts.index:
            return None
        return self._row_to_profile(self.accounts.loc[account_id])

    def suspicious_accounts(self, risk_tier: str = "HIGH", limit: int = 100) -> dict:
        df = self.accounts[self.accounts["risk_tier"] == risk_tier]
        df = df.sort_values("risk_score", ascending=False).head(limit)
        return {
            "risk_tier": risk_tier,
            "count": len(df),
            "accounts": [self._row_to_profile(row) for _, row in df.iterrows()],
        }

    # ---- patterns --------------------------------------------------------

    def get_patterns(self, typology: str | None = None, limit: int = 50) -> dict:
        typologies = sorted({p["typology"] for p in self.patterns})
        filtered = self.patterns
        if typology:
            filtered = [p for p in filtered if p["typology"].upper() == typology.upper()]
        return {
            "typologies": typologies,
            "total_patterns": len(filtered),
            "patterns": filtered[:limit],
        }

    # ---- graph -------------------------------------------------------------

    def path(self, source: str, target: str) -> dict:
        if source not in self.graph or target not in self.graph:
            return {"source": source, "target": target, "found": False, "path": [], "hops": []}
        try:
            node_path = nx.shortest_path(self.graph, source, target)
        except nx.NetworkXNoPath:
            return {"source": source, "target": target, "found": False, "path": [], "hops": []}
        hops = []
        for a, b in zip(node_path[:-1], node_path[1:]):
            d = self.graph.get_edge_data(a, b)
            hops.append({
                "from_id": a, "to_id": b,
                "shared_txn_count": d["shared_txn_count"],
                "total_amount_paid": d["total_amount_paid"],
                "laundering_txn_count": d["laundering_txn_count"],
            })
        return {"source": source, "target": target, "found": True, "path": node_path, "hops": hops}

    # ---- evaluation --------------------------------------------------------

    def evaluation(self) -> dict:
        return self.eval_stats


store = AnalyticsStore(
    settings.account_features_path, settings.suspicious_edges_path,
    settings.patterns_path, settings.eval_stats_path,
)
