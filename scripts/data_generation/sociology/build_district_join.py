"""
Joins real Census 2011 district socioeconomic data against the OLTP-derived
crime data (data/seed/fir.csv) by (state, district) name matching, and
writes a single precomputed analytics table that the sociological-insights
service loads at runtime.

Both sides of this join are real data - the census figures are the actual
2011 Census, and the crime *rates and mix* are NCRB-calibrated (individual
FIRs are synthetic, but the district-level distributions they're sampled
from are real - see data/schemas/synthetic_fir_schema.md). This is
different from the other two services, which only touch the synthetic
layer.

District names differ enough between the two sources (case, suffixes like
"RURAL"/"COMMR.", state naming like "ODISHA" vs "ORISSA") that they can't be
joined on a raw string match - see _normalize_district / _normalize_state /
STATE_ALIASES below. Matching is name-based, not administrative-code-based,
so it's an approximation - unmatched districts are dropped and the match
rate is reported (also written into the output as a comment-free summary
printed to stdout, and surfaced by the service's /districts endpoint).

Deliberately NOT computed here: any correlation involving SC/ST population
share or religion composition. Those fields are carried through into the
output CSV as neutral demographic context (they're public census data), but
the *service* that reads this file must never use them as a "driver" of a
crime-rate correlation - district-level correlation of caste/religion share
with crime rate is an ecological-fallacy trap that invites exactly the kind
of "this community is more criminal" misreading the platform's own fairness
principle (see scripts/data_generation/oltp/README.md's "Attribute
decoupling" section) exists to prevent. That's enforced in
backend/services/sociological-insights/app/analytics_store.py, not here -
this script just preserves the raw fields for transparency.

Usage:
    python scripts/data_generation/sociology/build_district_join.py
"""
import argparse
import difflib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CENSUS_PATH = ROOT / "data" / "raw" / "india-census-2011" / "india-districts-census-2011.csv"
FIR_PATH = ROOT / "data" / "seed" / "fir.csv"
OUT_PATH = ROOT / "data" / "processed" / "sociology" / "district_socioeconomic_crime.csv"
STATS_PATH = ROOT / "data" / "processed" / "sociology" / "match_stats.json"

FUZZY_MATCH_THRESHOLD = 0.82

VIOLENT_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY",
    "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY",
}
PROPERTY_TYPES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}

# Census state names -> NCRB/fir.csv state names, where they diverge beyond
# a simple "&" -> "AND" swap.
STATE_ALIASES = {
    "ORISSA": "ODISHA",
    "PONDICHERRY": "PUDUCHERRY",
    "NCT OF DELHI": "DELHI UT",
    "ANDAMAN AND NICOBAR ISLANDS": "A AND N ISLANDS",
    "DADRA AND NAGAR HAVELI": "D AND N HAVELI",
}

_DISTRICT_SUFFIX_PATTERN = re.compile(r"\b(COMMR\.?|RURAL|URBAN|CITY|TOTAL|DT\.?|GRP\.?|CP)\b")
_PARENS_PATTERN = re.compile(r"\([^)]*\)")


def _normalize_state(state: str) -> str:
    s = state.upper().strip()
    s = s.replace(" & ", " AND ")
    return STATE_ALIASES.get(s, s)


def _normalize_district(district: str) -> str:
    name = _PARENS_PATTERN.sub("", district.upper())
    name = _DISTRICT_SUFFIX_PATTERN.sub("", name)
    name = re.sub(r"[^A-Z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def load_census() -> pd.DataFrame:
    df = pd.read_csv(CENSUS_PATH)
    df["state_norm"] = df["State name"].map(_normalize_state)
    df["district_norm"] = df["District name"].map(_normalize_district)

    households = df["Households"].replace(0, pd.NA)
    population = df["Population"].replace(0, pd.NA)
    total_education = df["Total_Education"].replace(0, pd.NA)

    df["literacy_rate"] = df["Literate"] / population
    df["urbanization_rate"] = df["Urban_Households"] / households
    df["workforce_participation_rate"] = df["Workers"] / population
    df["higher_education_rate"] = (df["Higher_Education"] + df["Graduate_Education"]) / total_education
    df["amenity_index"] = (
        df["Housholds_with_Electric_Lighting"] / households
        + df["Households_with_Internet"] / households
        + df["Households_with_Computer"] / households
        + df["LPG_or_PNG_Households"] / households
    ) / 4.0

    # Carried through as neutral demographic context only - see module
    # docstring. Never fed into the service's correlation endpoints.
    df["sc_st_share"] = (df["SC"] + df["ST"]) / population
    df["hindu_share"] = df["Hindus"] / population
    df["muslim_share"] = df["Muslims"] / population
    df["christian_share"] = df["Christians"] / population
    df["sikh_share"] = df["Sikhs"] / population

    return df[[
        "state_norm", "district_norm", "State name", "District name", "Population",
        "literacy_rate", "urbanization_rate", "workforce_participation_rate",
        "higher_education_rate", "amenity_index",
        "sc_st_share", "hindu_share", "muslim_share", "christian_share", "sikh_share",
    ]].rename(columns={"State name": "census_state", "District name": "census_district"})


def load_fir_aggregates() -> pd.DataFrame:
    fir = pd.read_csv(FIR_PATH, dtype={"fir_id": str})
    fir["state_norm"] = fir["state"].map(_normalize_state)
    fir["district_norm"] = fir["district"].map(_normalize_district)
    fir["is_violent"] = fir["crime_type_code"].isin(VIOLENT_TYPES)
    fir["is_property"] = fir["crime_type_code"].isin(PROPERTY_TYPES)

    grouped = fir.groupby(["state_norm", "district_norm"]).agg(
        fir_state=("state", "first"),
        fir_district=("district", "first"),
        total_crimes=("fir_id", "count"),
        violent_crimes=("is_violent", "sum"),
        property_crimes=("is_property", "sum"),
    ).reset_index()
    grouped["violent_ratio"] = grouped["violent_crimes"] / grouped["total_crimes"]
    grouped["property_ratio"] = grouped["property_crimes"] / grouped["total_crimes"]
    return grouped


def match_districts(census: pd.DataFrame, fir_agg: pd.DataFrame) -> pd.DataFrame:
    fir_by_state: dict[str, pd.DataFrame] = {
        state: group for state, group in fir_agg.groupby("state_norm")
    }

    rows = []
    for census_row in census.itertuples(index=False):
        state_pool = fir_by_state.get(census_row.state_norm)
        if state_pool is None:
            continue

        exact = state_pool[state_pool["district_norm"] == census_row.district_norm]
        if len(exact) == 1:
            match_row, match_type, score = exact.iloc[0], "EXACT", 1.0
        else:
            candidates = state_pool["district_norm"].tolist()
            best = difflib.get_close_matches(census_row.district_norm, candidates, n=1, cutoff=FUZZY_MATCH_THRESHOLD)
            if not best:
                continue
            score = difflib.SequenceMatcher(None, census_row.district_norm, best[0]).ratio()
            match_row = state_pool[state_pool["district_norm"] == best[0]].iloc[0]
            match_type = "FUZZY"

        population = census_row.Population
        rows.append({
            "state": census_row.census_state,
            "district": census_row.census_district,
            "fir_district_label": match_row["fir_district"],
            "match_type": match_type,
            "match_score": round(score, 3),
            "population": population,
            "literacy_rate": census_row.literacy_rate,
            "urbanization_rate": census_row.urbanization_rate,
            "workforce_participation_rate": census_row.workforce_participation_rate,
            "higher_education_rate": census_row.higher_education_rate,
            "amenity_index": census_row.amenity_index,
            "sc_st_share": census_row.sc_st_share,
            "hindu_share": census_row.hindu_share,
            "muslim_share": census_row.muslim_share,
            "christian_share": census_row.christian_share,
            "sikh_share": census_row.sikh_share,
            "total_crimes": int(match_row["total_crimes"]),
            "violent_crimes": int(match_row["violent_crimes"]),
            "property_crimes": int(match_row["property_crimes"]),
            "violent_ratio": match_row["violent_ratio"],
            "property_ratio": match_row["property_ratio"],
            "crime_rate_per_100k": match_row["total_crimes"] / population * 100_000 if population else None,
            "violent_crime_rate_per_100k": match_row["violent_crimes"] / population * 100_000 if population else None,
            "property_crime_rate_per_100k": match_row["property_crimes"] / population * 100_000 if population else None,
        })

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-path", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    census = load_census()
    fir_agg = load_fir_aggregates()
    joined = match_districts(census, fir_agg)

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    joined.to_csv(args.out_path, index=False)

    n_census = len(census)
    n_matched = len(joined)
    n_exact = int((joined["match_type"] == "EXACT").sum())
    n_fuzzy = int((joined["match_type"] == "FUZZY").sum())

    stats = {
        "total_census_districts": n_census,
        "matched_districts": n_matched,
        "exact_matches": n_exact,
        "fuzzy_matches": n_fuzzy,
        "unmatched": n_census - n_matched,
        "match_rate": round(n_matched / n_census, 4) if n_census else 0.0,
        "fuzzy_match_threshold": FUZZY_MATCH_THRESHOLD,
    }
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, indent=2))

    print(f"Census districts: {n_census}")
    print(f"Matched to a crime-data district: {n_matched} ({n_matched / n_census:.1%})")
    print(f"  exact match: {n_exact}")
    print(f"  fuzzy match (>= {FUZZY_MATCH_THRESHOLD}): {n_fuzzy}")
    print(f"Unmatched (dropped): {n_census - n_matched}")
    print(f"Wrote {args.out_path}")
    print(f"Wrote {STATS_PATH}")


if __name__ == "__main__":
    main()
