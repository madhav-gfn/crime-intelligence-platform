"""
Runs etl_to_analytics.run_etl() against a built OLTP database, derives
network_edge.csv and offender_profile.csv from the resolved ACCUSED links
(same logic as the flat generator - see generate_synthetic_fir_data.py），
and writes all 5 analytics CSVs. This is what actually feeds
network-analysis and pattern-analytics.

Usage:
    python scripts/data_generation/oltp/write_analytics_csvs.py \
        --db-path data/processed/fir_system_oltp.sqlite --out-dir data/seed
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from etl_to_analytics import run_etl
from geo_lookup import get_coordinates

ROOT = Path(__file__).resolve().parents[3]


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", type=Path, default=ROOT / "data" / "processed" / "fir_system_oltp.sqlite")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "seed")
    args = ap.parse_args()

    print(f"Running ETL against {args.db_path} ...")
    person_rows, fir_rows, link_rows = run_etl(args.db_path, args.out_dir)

    fir_crime_type = {f["fir_id"]: f["crime_type_code"] for f in fir_rows}
    fir_weapon = {f["fir_id"]: f["weapon_used"] for f in fir_rows}

    for fir in fir_rows:
        lat, lon, precise = get_coordinates(fir["state"], fir["district"])
        fir["lat"], fir["lon"], fir["geo_precise"] = lat, lon, precise

    accused_by_fir = defaultdict(list)
    for row in link_rows:
        if row["role"] == "ACCUSED":
            accused_by_fir[row["fir_id"]].append(row["person_id"])

    edge_counts: dict[tuple[str, str], dict] = {}
    for fir_id, accused in accused_by_fir.items():
        accused = sorted(set(accused))
        for i in range(len(accused)):
            for j in range(i + 1, len(accused)):
                key = (accused[i], accused[j])
                edge_counts.setdefault(key, {"shared_fir_count": 0, "fir_ids": []})
                edge_counts[key]["shared_fir_count"] += 1
                edge_counts[key]["fir_ids"].append(fir_id)

    network_rows = [
        {"person_id_a": a, "person_id_b": b, "edge_type": "CO_ACCUSED",
         "shared_fir_count": v["shared_fir_count"], "fir_ids": "|".join(v["fir_ids"])}
        for (a, b), v in edge_counts.items()
    ]

    accused_case_counts = defaultdict(list)
    accused_weapon_flag = defaultdict(bool)
    for row in link_rows:
        if row["role"] == "ACCUSED":
            accused_case_counts[row["person_id"]].append(fir_crime_type[row["fir_id"]])
            if fir_weapon.get(row["fir_id"]):
                accused_weapon_flag[row["person_id"]] = True

    offender_rows = []
    for pid, crime_list in accused_case_counts.items():
        prior = len(crime_list)
        risk = "LOW"
        if prior >= 3 or (prior >= 2 and accused_weapon_flag[pid]):
            risk = "HIGH"
        elif prior >= 2 or accused_weapon_flag[pid]:
            risk = "MEDIUM"
        offender_rows.append({
            "person_id": pid, "prior_case_count": prior,
            "distinct_crime_types": "|".join(sorted(set(crime_list))),
            "used_weapon_ever": accused_weapon_flag[pid], "risk_tier": risk,
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "person.csv", list(person_rows.values()))
    write_csv(args.out_dir / "fir.csv", fir_rows)
    write_csv(args.out_dir / "fir_person_link.csv", link_rows)
    write_csv(args.out_dir / "network_edge.csv", network_rows)
    write_csv(args.out_dir / "offender_profile.csv", offender_rows)

    print(f"person.csv: {len(person_rows)} rows")
    print(f"fir.csv: {len(fir_rows)} rows")
    print(f"fir_person_link.csv: {len(link_rows)} rows")
    print(f"network_edge.csv: {len(network_rows)} rows")
    print(f"offender_profile.csv: {len(offender_rows)} rows")

    resolved_accused_persons = {row["person_id"] for row in link_rows if row["role"] == "ACCUSED"}
    total_accused_links = sum(1 for row in link_rows if row["role"] == "ACCUSED")
    print(f"\nEntity resolution: {total_accused_links} accused case-appearances resolved to "
          f"{len(resolved_accused_persons)} distinct persons "
          f"({total_accused_links - len(resolved_accused_persons)} repeat-offender re-links found)")


if __name__ == "__main__":
    main()
