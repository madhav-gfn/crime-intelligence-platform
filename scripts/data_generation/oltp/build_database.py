"""
Builds the full synthetic OLTP database matching
docs/architecture/Police_FIR_ER_Diagram.pdf: runs the DDL migrations, loads
reference/lookup data, then generates calibrated transactional case data.

Usage:
    python scripts/data_generation/oltp/build_database.py --n-cases 5000 --seed 42
"""
import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_data import load_reference_data
from transactional_data import generate_transactional_data

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = ROOT / "database" / "migrations"
CALIB_DIR = ROOT / "data" / "processed" / "calibration"
DEFAULT_DB_PATH = ROOT / "data" / "processed" / "fir_system_oltp.sqlite"
# Note: named for the schema, not the data's geographic scope. The ER diagram
# (docs/architecture/Police_FIR_ER_Diagram.pdf) is Karnataka Police
# Department's schema, but State/District are generic FK'd tables - this
# generator populates all 776 NCRB-calibrated districts nationwide (same
# scope as the flat generator), not Karnataka only.


def build(db_path: Path, n_cases: int, seed: int, start_year: int, end_year: int):
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.executescript(migration.read_text())

    rng = random.Random(seed)
    crime_type_mix = json.loads((CALIB_DIR / "crime_type_mix.json").read_text())
    district_weights = json.loads((CALIB_DIR / "district_weights.json").read_text())
    relationship_mix = json.loads((CALIB_DIR / "offender_relationship_mix.json").read_text())

    print(f"Loading reference data ({len(district_weights)} districts)...")
    ref = load_reference_data(conn, district_weights, rng)

    print(f"Generating {n_cases} cases ({start_year}-{end_year})...")
    generate_transactional_data(
        conn, ref, rng, crime_type_mix, district_weights, relationship_mix,
        n_cases, start_year, end_year,
    )

    cur = conn.cursor()
    print("\nRow counts:")
    for table in ["CaseMaster", "Victim", "Accused", "ComplainantDetails", "ArrestSurrender",
                   "ChargesheetDetails", "Inv_OccuranceTime", "ActSectionAssociation"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n}")

    conn.close()
    print(f"\nDatabase written to {db_path}")
    return db_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-cases", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start-year", type=int, default=2020)
    ap.add_argument("--end-year", type=int, default=2024)
    ap.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    args = ap.parse_args()
    build(args.db_path, args.n_cases, args.seed, args.start_year, args.end_year)


if __name__ == "__main__":
    main()
