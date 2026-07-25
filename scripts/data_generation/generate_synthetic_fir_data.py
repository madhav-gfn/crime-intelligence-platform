"""
Generates a synthetic FIR/offender/victim/network dataset calibrated against
real NCRB crime-type, geographic, and offender-relationship distributions
(data/processed/calibration/, produced by calibrate_ncrb.py).

Everything at the individual level (names, IDs, narratives) is synthetic.
See data/schemas/synthetic_fir_schema.md for the full schema and documented
assumptions/limitations.

Usage:
    python scripts/data_generation/generate_synthetic_fir_data.py --n-firs 5000 --seed 42
"""
import argparse
import csv
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from geo_lookup import get_coordinates
from name_pools import (
    FEMALE_FIRST_NAMES, MALE_FIRST_NAMES, OCCUPATIONS_BY_INCOME, STREET_TYPES, SURNAMES,
)
from crime_type_profiles import (
    DESCRIPTION_TEMPLATES, IPC_SECTION, NARRATIVE_TEMPLATES, PROPERTY_CRIME_TYPES,
    RELATIONSHIP_APPLICABLE_TYPES, STATUS_CLAUSE, WEAPON_RELEVANT_TYPES, WEAPONS,
)

ROOT = Path(__file__).resolve().parents[2]
CALIB_DIR = ROOT / "data" / "processed" / "calibration"
OUT_DIR = ROOT / "data" / "seed"

INCOME_BRACKETS = ["LOW", "LOWER_MIDDLE", "MIDDLE", "UPPER_MIDDLE", "HIGH"]
INCOME_WEIGHTS = [0.28, 0.30, 0.24, 0.13, 0.05]  # loosely informed by general Indian income distribution shape

STATUS_OPTIONS = ["UNDER_INVESTIGATION", "CHARGESHEETED", "TRIAL", "CONVICTED", "ACQUITTED", "CLOSED"]

# n_accused distribution: most FIRs have a single accused; multi-accused
# cases get rarer as group size grows, which is what lets a handful of
# larger cases seed realistic network clusters without every case being a "gang".
N_ACCUSED_OPTIONS = [1, 2, 3, 4, 5]
N_ACCUSED_WEIGHTS = [0.60, 0.20, 0.11, 0.06, 0.03]

REUSE_INDIVIDUAL_PROB = 0.35  # chance an accused slot reuses an existing offender instead of a fresh person
REUSE_CREW_PROB = 0.5  # for multi-accused FIRs, chance to reuse an existing co-offending crew intact


def load_calibration():
    crime_type_mix = json.loads((CALIB_DIR / "crime_type_mix.json").read_text())
    district_weights = json.loads((CALIB_DIR / "district_weights.json").read_text())
    relationship_mix = json.loads((CALIB_DIR / "offender_relationship_mix.json").read_text())
    return crime_type_mix, district_weights, relationship_mix


def weighted_sample(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def month_weight(crime_type: str, month: int) -> float:
    """Light criminology-informed seasonal heuristic, NOT calibrated from data
    (see schema doc's Known Limitations). Property crime ticks up around
    Oct-Nov (festival/wedding season, more valuables & travel) and summer
    (Apr-Jun, vacant homes); violent crime ticks up slightly in peak summer heat."""
    if crime_type in PROPERTY_CRIME_TYPES:
        if month in (10, 11, 4, 5):
            return 1.3
        return 1.0
    if crime_type in {"MURDER", "ATTEMPT_TO_MURDER", "RIOTS", "HURT_GRIEVOUS_HURT"}:
        if month in (4, 5, 6):
            return 1.2
        return 1.0
    return 1.0


def weekday_weight(crime_type: str, weekday: int) -> float:
    """weekday: 0=Mon..6=Sun. Friday/Saturday night skew for violent & property crime."""
    if weekday in (4, 5) and crime_type not in {"CHEATING", "CRIMINAL_BREACH_OF_TRUST", "CRUELTY_BY_HUSBAND_RELATIVES"}:
        return 1.25
    return 1.0


def sample_date(rng: random.Random, crime_type: str, start: date, end: date) -> date:
    span = (end - start).days
    # rejection-sample a handful of times against the seasonal/weekday weight, cheap and simple
    for _ in range(6):
        d = start + timedelta(days=rng.randint(0, span))
        w = month_weight(crime_type, d.month) * weekday_weight(crime_type, d.weekday())
        if rng.random() < min(w / 1.3, 1.0):
            return d
    return start + timedelta(days=rng.randint(0, span))


def sample_status(rng: random.Random, days_since_occurred: int) -> str:
    if days_since_occurred < 30:
        weights = [0.75, 0.15, 0.05, 0.02, 0.01, 0.02]
    elif days_since_occurred < 180:
        weights = [0.30, 0.35, 0.20, 0.06, 0.03, 0.06]
    else:
        weights = [0.10, 0.20, 0.25, 0.22, 0.08, 0.15]
    return weighted_sample(rng, STATUS_OPTIONS, weights)


class PersonFactory:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.counter = 0
        self.rows = []

    def create(self, state: str, district: str) -> str:
        self.counter += 1
        person_id = f"P-{self.counter:06d}"
        gender = self.rng.choice(["M", "F"])
        first = self.rng.choice(MALE_FIRST_NAMES if gender == "M" else FEMALE_FIRST_NAMES)
        last = self.rng.choice(SURNAMES)
        income = weighted_sample(self.rng, INCOME_BRACKETS, INCOME_WEIGHTS)
        occupation = self.rng.choice(OCCUPATIONS_BY_INCOME[income])
        row = {
            "person_id": person_id,
            "full_name": f"{first} {last}",
            "gender": gender,
            "age": self.rng.randint(16, 70),
            "address_state": state,
            "address_district": district,
            "occupation": occupation,
            "income_bracket": income,
        }
        self.rows.append(row)
        return person_id


class OffenderRegistry:
    """Tracks reusable accused persons and co-offending crews per district,
    so repeat offenders and organized groups emerge naturally instead of
    every FIR involving entirely fresh identities."""

    def __init__(self, rng: random.Random, person_factory: PersonFactory):
        self.rng = rng
        self.person_factory = person_factory
        self.district_pool: dict[str, list[str]] = defaultdict(list)  # district -> [person_id,...] (dup=usage weight)
        self.district_crews: dict[str, list[list[str]]] = defaultdict(list)

    def _new_accused(self, state: str, district: str) -> str:
        pid = self.person_factory.create(state, district)
        self.district_pool[district].append(pid)
        return pid

    def get_accused_group(self, state: str, district: str, n: int) -> list[str]:
        crews = self.district_crews[district]
        if n >= 2 and crews and self.rng.random() < REUSE_CREW_PROB:
            crew = self.rng.choice(crews)
            group = list(crew[:n])
            while len(group) < n:
                group.append(self._pick_or_create(state, district, exclude=group))
            return group

        group = []
        for _ in range(n):
            group.append(self._pick_or_create(state, district, exclude=group))

        if n >= 2:
            self.district_crews[district].append(group)
        return group

    def _pick_or_create(self, state: str, district: str, exclude: list[str]) -> str:
        pool = [p for p in self.district_pool[district] if p not in exclude]
        if pool and self.rng.random() < REUSE_INDIVIDUAL_PROB:
            return self.rng.choice(pool)  # duplicates in pool = preferential-attachment weighting
        pid = self._new_accused(state, district)
        return pid


def build_narrative(fir, victim_row, accused_names, relationship, crime_type) -> str:
    template = NARRATIVE_TEMPLATES.get(crime_type, NARRATIVE_TEMPLATES["DEFAULT"])
    if accused_names:
        who = accused_names[0] if len(accused_names) == 1 else f"{len(accused_names)} accused persons including {accused_names[0]}"
        rel_txt = f", known to the complainant as a {relationship.lower()}" if relationship and relationship != "STRANGER" else ""
        accused_clause = f"The complainant has named {who}{rel_txt}."
    else:
        accused_clause = "The identity of the accused is yet to be established."
    return template.format(
        date=fir["date_occurred"],
        time=fir["time_occurred"],
        police_station=fir["police_station"],
        victim=victim_row["full_name"] if victim_row else "the complainant",
        victim_age=victim_row["age"] if victim_row else "unknown",
        location=f"{fir['district']}, {fir['state']}",
        accused_clause=accused_clause,
        ipc_section=fir["ipc_section"],
        status_clause=STATUS_CLAUSE[fir["status"]],
        property_value=f"{fir['property_value_inr']:,.0f}" if fir.get("property_value_inr") else "an undisclosed amount",
    )


def generate(n_firs: int, seed: int, start_year: int, end_year: int):
    rng = random.Random(seed)
    crime_type_mix, district_weights, relationship_mix = load_calibration()

    crime_types = list(crime_type_mix.keys())
    crime_type_w = list(crime_type_mix.values())
    districts = district_weights
    district_w = [d["weight"] for d in districts]
    rel_types = list(relationship_mix.keys())
    rel_w = list(relationship_mix.values())

    persons = PersonFactory(rng)
    registry = OffenderRegistry(rng, persons)

    fir_rows = []
    link_rows = []

    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    for i in range(1, n_firs + 1):
        district_row = weighted_sample(rng, districts, district_w)
        state, district = district_row["state"], district_row["district"]
        lat, lon, precise = get_coordinates(state, district)

        crime_type = weighted_sample(rng, crime_types, crime_type_w)
        date_occurred = sample_date(rng, crime_type, start, end)
        report_lag = rng.randint(0, 5) if crime_type not in {"MURDER", "RAPE"} else rng.randint(0, 1)
        date_reported = min(date_occurred + timedelta(days=report_lag), end)
        days_since = (end - date_occurred).days
        status = sample_status(rng, days_since)

        fir_id = f"FIR-{date_occurred.year}-{i:06d}"
        police_station = f"{district.title()} {rng.choice(STREET_TYPES)} PS"

        victim_id = persons.create(state, district)
        victim_row = persons.rows[-1]

        n_accused = weighted_sample(rng, N_ACCUSED_OPTIONS, N_ACCUSED_WEIGHTS)
        accused_ids = registry.get_accused_group(state, district, n_accused)
        accused_rows = [next(r for r in persons.rows if r["person_id"] == pid) for pid in accused_ids]
        accused_names = [r["full_name"] for r in accused_rows]

        relationship = None
        if crime_type in RELATIONSHIP_APPLICABLE_TYPES:
            relationship = weighted_sample(rng, rel_types, rel_w)

        property_value = None
        if crime_type in PROPERTY_CRIME_TYPES or crime_type == "CHEATING":
            # rough log-normal-ish spread: many small thefts, a long tail of big-ticket cases
            property_value = round(rng.lognormvariate(9.5, 1.1), -2)

        weapon = rng.choice(WEAPONS) if crime_type in WEAPON_RELEVANT_TYPES and rng.random() < 0.6 else None

        fir = {
            "fir_id": fir_id,
            "state": state,
            "district": district,
            "police_station": police_station,
            "lat": lat,
            "lon": lon,
            "geo_precise": precise,
            "date_reported": date_reported.isoformat(),
            "time_reported": f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}",
            "date_occurred": date_occurred.isoformat(),
            "time_occurred": f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}",
            "crime_type_code": crime_type,
            "ipc_section": IPC_SECTION[crime_type],
            "crime_description": DESCRIPTION_TEMPLATES[crime_type].format(
                victim=victim_row["full_name"],
                location=f"{district}, {state}",
                accused_desc=(relationship.lower() if relationship and relationship != "STRANGER" else "an unidentified person"),
            ),
            "weapon_used": weapon,
            "property_value_inr": property_value,
            "status": status,
        }
        fir["narrative"] = build_narrative(fir, victim_row, accused_names, relationship, crime_type)
        fir_rows.append(fir)

        link_rows.append({"fir_id": fir_id, "person_id": victim_id, "role": "VICTIM", "relationship_to_victim": ""})
        for pid in accused_ids:
            link_rows.append({
                "fir_id": fir_id, "person_id": pid, "role": "ACCUSED",
                "relationship_to_victim": relationship or "",
            })
        if rng.random() < 0.25:
            witness_id = persons.create(state, district)
            link_rows.append({"fir_id": fir_id, "person_id": witness_id, "role": "WITNESS", "relationship_to_victim": ""})

    # network edges: any two ACCUSED sharing an FIR
    accused_by_fir = defaultdict(list)
    for row in link_rows:
        if row["role"] == "ACCUSED":
            accused_by_fir[row["fir_id"]].append(row["person_id"])

    edge_counts: dict[tuple[str, str], dict] = {}
    for fir_id, accused in accused_by_fir.items():
        accused = sorted(set(accused))
        for idx_a in range(len(accused)):
            for idx_b in range(idx_a + 1, len(accused)):
                key = (accused[idx_a], accused[idx_b])
                if key not in edge_counts:
                    edge_counts[key] = {"shared_fir_count": 0, "fir_ids": []}
                edge_counts[key]["shared_fir_count"] += 1
                edge_counts[key]["fir_ids"].append(fir_id)

    network_rows = [
        {
            "person_id_a": a, "person_id_b": b, "edge_type": "CO_ACCUSED",
            "shared_fir_count": v["shared_fir_count"], "fir_ids": "|".join(v["fir_ids"]),
        }
        for (a, b), v in edge_counts.items()
    ]

    # offender profile rollup
    accused_case_counts = defaultdict(list)
    accused_weapon_flag = defaultdict(bool)
    fir_by_id = {f["fir_id"]: f for f in fir_rows}
    for row in link_rows:
        if row["role"] == "ACCUSED":
            fir = fir_by_id[row["fir_id"]]
            accused_case_counts[row["person_id"]].append(fir["crime_type_code"])
            if fir["weapon_used"]:
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
            "person_id": pid,
            "prior_case_count": prior,
            "distinct_crime_types": "|".join(sorted(set(crime_list))),
            "used_weapon_ever": accused_weapon_flag[pid],
            "risk_tier": risk,
        })

    return persons.rows, fir_rows, link_rows, network_rows, offender_rows


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
    ap.add_argument("--n-firs", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start-year", type=int, default=2020)
    ap.add_argument("--end-year", type=int, default=2024)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    persons, firs, links, edges, offenders = generate(args.n_firs, args.seed, args.start_year, args.end_year)

    write_csv(OUT_DIR / "person.csv", persons)
    write_csv(OUT_DIR / "fir.csv", firs)
    write_csv(OUT_DIR / "fir_person_link.csv", links)
    write_csv(OUT_DIR / "network_edge.csv", edges)
    write_csv(OUT_DIR / "offender_profile.csv", offenders)

    print(f"person.csv: {len(persons)} rows")
    print(f"fir.csv: {len(firs)} rows")
    print(f"fir_person_link.csv: {len(links)} rows")
    print(f"network_edge.csv: {len(edges)} rows")
    print(f"offender_profile.csv: {len(offenders)} rows")


if __name__ == "__main__":
    main()
