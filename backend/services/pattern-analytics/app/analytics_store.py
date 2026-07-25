"""
Loads the synthetic FIR seed dataset and computes crime pattern analytics:
geospatial hotspot clustering (DBSCAN), district severity tiering
(PCA+KMeans), temporal trends, emerging-spike detection, and MO-similarity
case matching. Mirrors the analytical approach documented in
docs/architecture/Conversational Crime Analytics AI Research.md's
"Geospatial-Temporal Crime Pattern Analytics" section.
"""
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.taxonomy import PROPERTY_TYPES, UNRESOLVED_STATUSES, VIOLENT_TYPES

EARTH_RADIUS_KM = 6371.0088
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_BUCKETS = [(0, 6, "NIGHT_00_06"), (6, 12, "MORNING_06_12"), (12, 18, "AFTERNOON_12_18"), (18, 24, "EVENING_18_24")]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _time_bucket(hour: int) -> str:
    for start, end, label in TIME_BUCKETS:
        if start <= hour < end:
            return label
    return TIME_BUCKETS[-1][2]


def _shannon_entropy(counts: pd.Series) -> float:
    probs = counts / counts.sum()
    entropy = -(probs * np.log(probs)).sum()
    max_entropy = np.log(len(counts)) if len(counts) > 1 else 1.0
    return float(entropy / max_entropy) if max_entropy > 0 else 0.0


class AnalyticsStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.df: pd.DataFrame | None = None

    def load(self):
        self.df = pd.read_csv(self.data_dir / "fir.csv")
        self.df["date_occurred"] = pd.to_datetime(self.df["date_occurred"])
        self.df["hour"] = self.df["time_occurred"].str.split(":").str[0].astype(int)
        self.df["weekday"] = self.df["date_occurred"].dt.day_name()
        self.df["month_bucket"] = self.df["date_occurred"].dt.to_period("M").astype(str)
        self.df["time_bucket"] = self.df["hour"].apply(_time_bucket)
        return self

    def _filtered(self, crime_type: str | None = None, district: str | None = None,
                  start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        df = self.df
        if crime_type:
            df = df[df["crime_type_code"] == crime_type]
        if district:
            df = df[df["district"].str.contains(district, case=False, na=False)]
        if start_date:
            df = df[df["date_occurred"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date_occurred"] <= pd.to_datetime(end_date)]
        return df

    # ---- dataset stats -----------------------------------------------------

    def stats(self) -> dict:
        df = self.df
        return {
            "total_firs": len(df),
            "date_range_start": df["date_occurred"].min().date().isoformat(),
            "date_range_end": df["date_occurred"].max().date().isoformat(),
            "distinct_districts": df["district"].nunique(),
            "distinct_crime_types": df["crime_type_code"].nunique(),
            "crime_type_counts": df["crime_type_code"].value_counts().to_dict(),
        }

    # ---- hotspots (DBSCAN) --------------------------------------------------

    def hotspots(self, crime_type=None, district=None, start_date=None, end_date=None,
                 eps_km: float = 15.0, min_points: int = 5) -> dict:
        df = self._filtered(crime_type, district, start_date, end_date)
        filters = {"crime_type": crime_type, "district": district, "start_date": start_date, "end_date": end_date}

        if len(df) < min_points:
            return {
                "filters": filters, "eps_km": eps_km, "min_points": min_points,
                "total_points_considered": len(df), "noise_points": len(df), "clusters": [],
            }

        coords_rad = np.radians(df[["lat", "lon"]].to_numpy())
        db = DBSCAN(eps=eps_km / EARTH_RADIUS_KM, min_samples=min_points, metric="haversine")
        labels = db.fit_predict(coords_rad)
        df = df.assign(_cluster=labels)

        clusters = []
        for cluster_id in sorted(c for c in set(labels) if c != -1):
            members = df[df["_cluster"] == cluster_id]
            centroid_lat = members["lat"].mean()
            centroid_lon = members["lon"].mean()
            radius_km = max(
                (_haversine_km(centroid_lat, centroid_lon, r.lat, r.lon) for r in members.itertuples()),
                default=0.0,
            )
            clusters.append({
                "cluster_id": int(cluster_id),
                "point_count": len(members),
                "centroid_lat": round(float(centroid_lat), 5),
                "centroid_lon": round(float(centroid_lon), 5),
                "radius_km": round(radius_km, 2),
                "top_district": members["district"].mode().iloc[0],
                "crime_type_breakdown": members["crime_type_code"].value_counts().to_dict(),
                "sample_fir_ids": members["fir_id"].head(5).tolist(),
                # Low, and this cluster is likely an artifact of several low-volume
                # districts' deterministic jittered fallback coordinates landing near
                # each other, rather than a genuine intra-district hotspot - see
                # data/schemas/synthetic_fir_schema.md "Known limitations".
                "geo_precise_fraction": round(float(members["geo_precise"].mean()), 3),
            })
        clusters.sort(key=lambda c: -c["point_count"])

        return {
            "filters": filters, "eps_km": eps_km, "min_points": min_points,
            "total_points_considered": len(df), "noise_points": int((labels == -1).sum()),
            "clusters": clusters,
        }

    # ---- district severity (PCA + KMeans) -----------------------------------

    def district_severity(self, min_crimes: int = 10, n_tiers: int = 3) -> dict:
        df = self.df
        rows = []
        for (state, district), grp in df.groupby(["state", "district"]):
            total = len(grp)
            if total < min_crimes:
                continue
            violent = grp["crime_type_code"].isin(VIOLENT_TYPES).sum()
            property_ = grp["crime_type_code"].isin(PROPERTY_TYPES).sum()
            unresolved = grp["status"].isin(UNRESOLVED_STATUSES).sum()
            avg_property_value = grp["property_value_inr"].dropna().mean()
            rows.append({
                "state": state, "district": district, "total_crimes": total,
                "violent_crime_ratio": violent / total,
                "property_crime_ratio": property_ / total,
                "avg_property_value_inr": float(avg_property_value) if not pd.isna(avg_property_value) else 0.0,
                "crime_type_diversity": _shannon_entropy(grp["crime_type_code"].value_counts()),
                "unresolved_ratio": unresolved / total,
            })

        if len(rows) < n_tiers:
            return {"min_crimes_threshold": min_crimes, "districts_included": len(rows), "tiers": []}

        feat_df = pd.DataFrame(rows)
        feature_cols = ["total_crimes", "violent_crime_ratio", "property_crime_ratio", "unresolved_ratio", "crime_type_diversity"]
        X = feat_df[feature_cols].copy()
        X["total_crimes"] = np.log1p(X["total_crimes"])  # volume is heavy-tailed, compress it
        X_scaled = StandardScaler().fit_transform(X)

        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(X_scaled)

        km = KMeans(n_clusters=n_tiers, random_state=42, n_init=10)
        cluster_labels = km.fit_predict(X_scaled)
        feat_df["cluster_label"] = cluster_labels
        feat_df["pca_x"] = coords[:, 0]
        feat_df["pca_y"] = coords[:, 1]

        # Rank clusters by a composite severity score (volume + violence), not
        # by KMeans label id (which is arbitrary), so tier names are meaningful.
        z_crimes = (np.log1p(feat_df["total_crimes"]) - np.log1p(feat_df["total_crimes"]).mean()) / np.log1p(feat_df["total_crimes"]).std()
        z_violent = (feat_df["violent_crime_ratio"] - feat_df["violent_crime_ratio"].mean()) / feat_df["violent_crime_ratio"].std()
        feat_df["severity_score"] = 0.6 * z_crimes + 0.4 * z_violent
        cluster_rank = feat_df.groupby("cluster_label")["severity_score"].mean().sort_values().index.tolist()
        tier_names = ["LOW", "MEDIUM", "HIGH"] if n_tiers == 3 else [f"TIER_{i}" for i in range(n_tiers)]
        cluster_to_tier = {cluster_id: tier_names[rank] for rank, cluster_id in enumerate(cluster_rank)}
        feat_df["severity_tier"] = feat_df["cluster_label"].map(cluster_to_tier)

        tiers = [
            {
                "district": r.district, "state": r.state, "total_crimes": int(r.total_crimes),
                "violent_crime_ratio": round(r.violent_crime_ratio, 4),
                "property_crime_ratio": round(r.property_crime_ratio, 4),
                "avg_property_value_inr": round(r.avg_property_value_inr, 2),
                "crime_type_diversity": round(r.crime_type_diversity, 4),
                "unresolved_ratio": round(r.unresolved_ratio, 4),
                "severity_tier": r.severity_tier,
                "pca_x": round(r.pca_x, 4), "pca_y": round(r.pca_y, 4),
            }
            for r in feat_df.itertuples()
        ]
        tiers.sort(key=lambda t: -t["total_crimes"])
        return {"min_crimes_threshold": min_crimes, "districts_included": len(tiers), "tiers": tiers}

    # ---- temporal trends -----------------------------------------------------

    def trends(self, granularity: str, crime_type=None, district=None) -> dict:
        df = self._filtered(crime_type, district)
        filters = {"crime_type": crime_type, "district": district}

        if granularity == "monthly":
            counts = df.groupby("month_bucket").size().sort_index()
            points = [{"bucket": k, "count": int(v)} for k, v in counts.items()]
        elif granularity == "weekday":
            counts = df.groupby("weekday").size().reindex(WEEKDAY_NAMES, fill_value=0)
            points = [{"bucket": k, "count": int(v)} for k, v in counts.items()]
        elif granularity == "hourly":
            counts = df.groupby("hour").size().reindex(range(24), fill_value=0)
            points = [{"bucket": f"{k:02d}:00", "count": int(v)} for k, v in counts.items()]
        else:
            raise ValueError(f"unknown granularity: {granularity}")

        return {"granularity": granularity, "filters": filters, "points": points}

    # ---- emerging hotspot / spike detection -----------------------------------

    def emerging(self, recent_days: int = 90, baseline_days: int = 180, min_recent_count: int = 5) -> dict:
        df = self.df
        end = df["date_occurred"].max()
        recent_start = end - pd.Timedelta(days=recent_days)
        baseline_start = recent_start - pd.Timedelta(days=baseline_days)

        recent = df[(df["date_occurred"] > recent_start) & (df["date_occurred"] <= end)]
        baseline = df[(df["date_occurred"] > baseline_start) & (df["date_occurred"] <= recent_start)]

        recent_counts = recent.groupby(["state", "district", "crime_type_code"]).size()
        baseline_counts = baseline.groupby(["state", "district", "crime_type_code"]).size()

        alerts = []
        for key, recent_count in recent_counts.items():
            if recent_count < min_recent_count:
                continue
            state, district, crime_type = key
            baseline_count = int(baseline_counts.get(key, 0))
            if baseline_count == 0:
                pct_change = None
                reason = "new pattern: no comparable activity in the baseline period"
            else:
                expected_recent = baseline_count * (recent_days / baseline_days)
                pct_change = round(((recent_count - expected_recent) / expected_recent) * 100, 1)
                if pct_change < 50:
                    continue
                reason = f"{pct_change:+.0f}% vs. baseline-implied rate"
            alerts.append({
                "district": district, "state": state, "crime_type_code": crime_type,
                "recent_count": int(recent_count), "baseline_count": baseline_count,
                "recent_period_days": recent_days, "baseline_period_days": baseline_days,
                "pct_change": pct_change, "flagged_reason": reason,
            })

        alerts.sort(key=lambda a: (-(a["pct_change"] or 1e9), -a["recent_count"]))
        return {
            "recent_window_days": recent_days, "baseline_window_days": baseline_days,
            "min_recent_count": min_recent_count, "alerts": alerts[:30],
        }

    # ---- MO similarity --------------------------------------------------------

    def similar_cases(self, fir_id: str, top_n: int = 10) -> dict | None:
        df = self.df
        if fir_id not in df["fir_id"].values:
            return None
        source_idx = df.index[df["fir_id"] == fir_id][0]

        feature_df = pd.get_dummies(df[["crime_type_code", "weapon_used", "time_bucket"]].fillna("NONE"))
        sim = cosine_similarity(feature_df.iloc[[source_idx]], feature_df)[0]

        result_df = df.copy()
        result_df["_sim"] = sim
        source_row = df.loc[source_idx]
        same_district = (result_df["district"] == source_row["district"]).astype(float) * 0.05
        same_state = (result_df["state"] == source_row["state"]).astype(float) * 0.02
        result_df["_sim"] = (result_df["_sim"] + same_district + same_state).clip(upper=1.0)
        result_df = result_df.drop(index=source_idx).sort_values("_sim", ascending=False).head(top_n)

        results = []
        for _, row in result_df.iterrows():
            matching = []
            if row["crime_type_code"] == source_row["crime_type_code"]:
                matching.append("same crime type")
            if pd.notna(row["weapon_used"]) and row["weapon_used"] == source_row["weapon_used"]:
                matching.append("same weapon")
            if row["time_bucket"] == source_row["time_bucket"]:
                matching.append("same time-of-day window")
            if row["district"] == source_row["district"]:
                matching.append("same district")
            elif row["state"] == source_row["state"]:
                matching.append("same state")
            results.append({
                "fir_id": row["fir_id"], "similarity": round(float(row["_sim"]), 4),
                "crime_type_code": row["crime_type_code"], "district": row["district"], "state": row["state"],
                "date_occurred": row["date_occurred"].date().isoformat(), "status": row["status"],
                "matching_features": matching,
            })

        return {
            "source_fir_id": fir_id, "source_crime_type": source_row["crime_type_code"],
            "top_n": top_n, "results": results,
        }


store = AnalyticsStore(settings.data_seed_dir)
