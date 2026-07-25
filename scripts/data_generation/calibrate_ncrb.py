"""
Derives sampling distributions from real NCRB district-wise crime data
(data/raw/ncrb-india-crime/district-wise/) so the synthetic FIR generator
produces crime-type mixes and geographic hotspot concentration that match
real reported patterns, instead of uniform-random noise.

Output: data/processed/calibration/{crime_type_mix.json, district_weights.json}
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ncrb-india-crime" / "district-wise" / "01_District_wise_crimes_committed_IPC_2001_2012.csv"
RELATIONSHIP_RAW = (
    ROOT / "data" / "raw" / "ncrb-india-crime" / "rajanand-crime-in-india"
    / "crime" / "21_Offenders_known_to_the_victim.csv"
)
OUT_DIR = ROOT / "data" / "processed" / "calibration"

# NCRB column -> our internal crime_type code + human label.
# A few narrow/legal-procedure columns (counterfeiting, importation of girls,
# custodial rape as a separate line, etc.) are folded into nearby categories
# or OTHER so the resulting mix is usable as sampling weights, not a legal taxonomy.
CRIME_TYPE_MAP = {
    "MURDER": "MURDER",
    "ATTEMPT TO MURDER": "ATTEMPT_TO_MURDER",
    "CULPABLE HOMICIDE NOT AMOUNTING TO MURDER": "CULPABLE_HOMICIDE",
    "RAPE": "RAPE",
    "KIDNAPPING & ABDUCTION": "KIDNAPPING_ABDUCTION",
    "DACOITY": "DACOITY",
    "ROBBERY": "ROBBERY",
    "BURGLARY": "BURGLARY",
    "THEFT": "THEFT",
    "AUTO THEFT": "AUTO_THEFT",
    "OTHER THEFT": "OTHER_THEFT",
    "RIOTS": "RIOTS",
    "CRIMINAL BREACH OF TRUST": "CRIMINAL_BREACH_OF_TRUST",
    "CHEATING": "CHEATING",
    "ARSON": "ARSON",
    "HURT/GREVIOUS HURT": "HURT_GRIEVOUS_HURT",
    "DOWRY DEATHS": "DOWRY_DEATH",
    "ASSAULT ON WOMEN WITH INTENT TO OUTRAGE HER MODESTY": "ASSAULT_ON_WOMEN_MODESTY",
    "CRUELTY BY HUSBAND OR HIS RELATIVES": "CRUELTY_BY_HUSBAND_RELATIVES",
    "CAUSING DEATH BY NEGLIGENCE": "DEATH_BY_NEGLIGENCE",
    "OTHER IPC CRIMES": "OTHER_IPC_CRIMES",
}

CALIBRATION_YEAR = 2012  # most recent year in this dataset


def load_clean():
    df = pd.read_csv(RAW)
    # NCRB dumps include per-state "TOTAL" rollup rows under DISTRICT - drop them
    # to avoid double-counting every district's crimes a second time.
    df = df[~df["DISTRICT"].str.contains("TOTAL", case=False, na=False)].copy()
    return df


def build_crime_type_mix(df: pd.DataFrame) -> dict:
    latest = df[df["YEAR"] == CALIBRATION_YEAR]
    sums = latest[list(CRIME_TYPE_MAP.keys())].sum()
    total = sums.sum()
    mix = {CRIME_TYPE_MAP[col]: round(sums[col] / total, 6) for col in CRIME_TYPE_MAP}
    return dict(sorted(mix.items(), key=lambda kv: -kv[1]))


def build_district_weights(df: pd.DataFrame) -> list[dict]:
    latest = df[df["YEAR"] == CALIBRATION_YEAR]
    grouped = (
        latest.groupby(["STATE/UT", "DISTRICT"])["TOTAL IPC CRIMES"]
        .sum()
        .reset_index()
    )
    grouped = grouped[grouped["TOTAL IPC CRIMES"] > 0]
    total = grouped["TOTAL IPC CRIMES"].sum()
    grouped["weight"] = grouped["TOTAL IPC CRIMES"] / total
    grouped = grouped.sort_values("weight", ascending=False)
    return [
        {
            "state": row["STATE/UT"].strip(),
            "district": row["DISTRICT"].strip(),
            "reported_ipc_crimes_2012": int(row["TOTAL IPC CRIMES"]),
            "weight": round(row["weight"], 8),
        }
        for _, row in grouped.iterrows()
    ]


def build_known_offender_relationship_mix() -> dict:
    """
    Calibrated from NCRB's "offenders known to the victim" breakdown
    (crimes against women dataset). This source only covers cases where the
    offender WAS known to the victim, broken into sub-categories - it does not
    give a known-vs-stranger split. The known-vs-stranger ratio below (75/25)
    is a documented assumption from general criminology literature on crimes
    against the person, not derived from this NCRB file - flagged here so
    downstream consumers don't mistake it for a calibrated number.
    """
    df = pd.read_csv(RELATIONSHIP_RAW)
    cols = {
        "No_of_Cases_in_which_offenders_were_Neighbours": "NEIGHBOR",
        "No_of_Cases_in_which_offenders_were_Other_Known_persons": "ACQUAINTANCE",
        "No_of_Cases_in_which_offenders_were_Parentsclose_family_members": "FAMILY",
        "No_of_Cases_in_which_offenders_were_Relatives": "RELATIVE",
    }
    totals = df[list(cols.keys())].sum()
    known_total = totals.sum()
    known_fraction_of_all_cases = 0.75  # documented assumption, see docstring
    mix = {"STRANGER": round(1 - known_fraction_of_all_cases, 4)}
    for col, label in cols.items():
        mix[label] = round((totals[col] / known_total) * known_fraction_of_all_cases, 4)
    return mix


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_clean()

    crime_type_mix = build_crime_type_mix(df)
    (OUT_DIR / "crime_type_mix.json").write_text(json.dumps(crime_type_mix, indent=2))
    print(f"crime_type_mix.json: {len(crime_type_mix)} categories, calibrated on {CALIBRATION_YEAR}")

    district_weights = build_district_weights(df)
    (OUT_DIR / "district_weights.json").write_text(json.dumps(district_weights, indent=2))
    print(f"district_weights.json: {len(district_weights)} state/district pairs")
    print("Top 5 districts by weight:")
    for row in district_weights[:5]:
        print(f"  {row['district']}, {row['state']}: {row['weight']:.4f}")

    relationship_mix = build_known_offender_relationship_mix()
    (OUT_DIR / "offender_relationship_mix.json").write_text(json.dumps(relationship_mix, indent=2))
    print(f"offender_relationship_mix.json: {relationship_mix}")


if __name__ == "__main__":
    main()
