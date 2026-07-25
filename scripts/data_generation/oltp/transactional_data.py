"""
Populates CaseMaster and every child table (Inv_OccuranceTime,
ComplainantDetails, ActSectionAssociation, Victim, Accused, ArrestSurrender,
inv_arrestsurrenderaccused, ChargesheetDetails), calibrated against the same
real NCRB distributions used by the flat generator
(scripts/data_generation/generate_synthetic_fir_data.py).

Important structural note: the real ER schema has NO table linking an
accused person across different CaseMaster rows - Accused.AccusedMasterID
is scoped to a single case, there's no cross-case "Person" master. A real
deployment would need an entity-resolution step (name/demographic matching)
to reconstruct "this is the same repeat offender" across cases - exactly the
transliteration/spelling-variation problem the platform's own research doc
flags. This generator models that faithfully: it tracks a "true identity"
internally to decide *which* cases a repeat offender appears in, but writes
each appearance as an independent Accused row with a name that has a small
chance of spelling drift - it does NOT write any cross-case identity key.
oltp/etl.py has to rediscover repeat offenders via matching, same as a real
system would. See that module for the resolution logic.
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geo_lookup import get_coordinates
from name_pools import FEMALE_FIRST_NAMES, MALE_FIRST_NAMES, OCCUPATIONS_BY_INCOME, SURNAMES
from crime_type_profiles import DESCRIPTION_TEMPLATES

from reference_data import ACT_SECTION_MAP, CASTE_CATEGORIES, HEINOUS_CRIME_TYPES, RefData, RELIGIONS

DEATH_RELATED_TYPES = {"MURDER", "CULPABLE_HOMICIDE", "DOWRY_DEATH", "DEATH_BY_NEGLIGENCE"}
CASE_CATEGORY_PREFIX = {"FIR": "1", "UDR": "3", "PAR": "4", "Zero FIR": "8"}
STATUS_OPTIONS = ["UNDER_INVESTIGATION", "CHARGESHEETED", "TRIAL", "CONVICTED", "ACQUITTED", "CLOSED"]
N_ACCUSED_OPTIONS = [1, 2, 3, 4, 5]
N_ACCUSED_WEIGHTS = [0.60, 0.20, 0.11, 0.06, 0.03]
REUSE_INDIVIDUAL_PROB = 0.35
REUSE_CREW_PROB = 0.5
SPELLING_VARIATION_PROB = 0.15

_VOWEL_DRIFT = [("i", "ee"), ("u", "oo"), ("v", "w"), ("oo", "u"), ("ee", "i")]


def _drift_spelling(rng: random.Random, name: str) -> str:
    """Simulates the transliteration/spelling-variation problem the platform's
    own research doc calls out - a crude but real analogue of how the same
    person's name ends up spelled differently across independently-filed FIRs."""
    for src, dst in rng.sample(_VOWEL_DRIFT, len(_VOWEL_DRIFT)):
        if src in name.lower():
            idx = name.lower().index(src)
            return name[:idx] + dst + name[idx + len(src):]
    return name[:-1] if len(name) > 3 else name


def _weighted(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


class AccusedIdentityRegistry:
    """Tracks 'true' offender identities per district for preferential reuse
    across cases (repeat offenders / organized crews), without ever writing
    that identity into the OLTP schema itself - see module docstring."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.pool: dict[tuple, list[dict]] = {}
        self.crews: dict[tuple, list[list[dict]]] = {}

    def _new_identity(self, gender: str, base_age: int, year: int) -> dict:
        first = self.rng.choice(MALE_FIRST_NAMES if gender == "M" else FEMALE_FIRST_NAMES)
        last = self.rng.choice(SURNAMES)
        return {"name": f"{first} {last}", "gender": gender, "base_age": base_age, "base_year": year}

    def _materialize(self, identity: dict, case_year: int) -> dict:
        age = max(16, identity["base_age"] + (case_year - identity["base_year"]))
        name = identity["name"]
        if self.rng.random() < SPELLING_VARIATION_PROB:
            name = _drift_spelling(self.rng, name)
        return {"name": name, "age": age, "gender": identity["gender"]}

    def group(self, key: tuple, n: int, case_year: int) -> list[dict]:
        crews = self.crews.setdefault(key, [])
        pool = self.pool.setdefault(key, [])

        if n >= 2 and crews and self.rng.random() < REUSE_CREW_PROB:
            base_crew = self.rng.choice(crews)
            identities = list(base_crew[:n])
            while len(identities) < n:
                identities.append(self._pick_or_create(key, case_year))
        else:
            identities = [self._pick_or_create(key, case_year) for _ in range(n)]
            if n >= 2:
                crews.append(identities)

        return [self._materialize(ident, case_year) for ident in identities]

    def _pick_or_create(self, key: tuple, case_year: int) -> dict:
        pool = self.pool[key]
        if pool and self.rng.random() < REUSE_INDIVIDUAL_PROB:
            return self.rng.choice(pool)
        gender = self.rng.choice(["M", "F"])
        identity = self._new_identity(gender, self.rng.randint(18, 55), case_year)
        pool.append(identity)
        return identity


def _sample_date(rng: random.Random, crime_type: str, start: date, end: date) -> date:
    span = (end - start).days
    for _ in range(6):
        d = start + timedelta(days=rng.randint(0, span))
        month_boost = 1.3 if crime_type not in {"CHEATING", "CRIMINAL_BREACH_OF_TRUST"} and d.month in (10, 11, 4, 5) else 1.0
        weekday_boost = 1.25 if d.weekday() in (4, 5) else 1.0
        if rng.random() < min(month_boost * weekday_boost / 1.3, 1.0):
            return d
    return start + timedelta(days=rng.randint(0, span))


def _sample_status(rng: random.Random, days_since: int) -> str:
    if days_since < 30:
        weights = [0.75, 0.15, 0.05, 0.02, 0.01, 0.02]
    elif days_since < 180:
        weights = [0.30, 0.35, 0.20, 0.06, 0.03, 0.06]
    else:
        weights = [0.10, 0.20, 0.25, 0.22, 0.08, 0.15]
    return _weighted(rng, STATUS_OPTIONS, weights)


def _random_time(rng: random.Random) -> str:
    return f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00"


def generate_transactional_data(
    conn: sqlite3.Connection, ref: RefData, rng: random.Random,
    crime_type_mix: dict, district_weights: list[dict], relationship_mix: dict,
    n_cases: int, start_year: int, end_year: int,
):
    cur = conn.cursor()
    crime_types = list(crime_type_mix.keys())
    crime_type_w = list(crime_type_mix.values())
    district_w = [d["weight"] for d in district_weights]
    rel_types = list(relationship_mix.keys())
    rel_w = list(relationship_mix.values())

    start, end = date(start_year, 1, 1), date(end_year, 12, 31)
    accused_registry = AccusedIdentityRegistry(rng)
    crime_no_counters: dict[tuple, int] = {}
    all_occupations = sorted({occ for occs in OCCUPATIONS_BY_INCOME.values() for occ in occs})

    for _ in range(n_cases):
        d = _weighted(rng, district_weights, district_w)
        key = (d["state"], d["district"])
        crime_type = _weighted(rng, crime_types, crime_type_w)

        date_occurred = _sample_date(rng, crime_type, start, end)
        report_lag = rng.randint(0, 1) if crime_type in {"MURDER", "RAPE"} else rng.randint(0, 5)
        date_reported = min(date_occurred + timedelta(days=report_lag), end)

        category = "FIR"
        if crime_type in DEATH_RELATED_TYPES and rng.random() < 0.08:
            category = "UDR"
        elif rng.random() < 0.02:
            category = "Zero FIR"
        elif rng.random() < 0.01:
            category = "PAR"

        unit_id = rng.choice(ref.ps_units_by_district[key])
        district_id = ref.district_id[key]
        year = date_occurred.year
        counter_key = (unit_id, category, year)
        crime_no_counters[counter_key] = crime_no_counters.get(counter_key, 0) + 1
        serial = crime_no_counters[counter_key]
        crime_no = f"{CASE_CATEGORY_PREFIX[category]}{district_id:04d}{unit_id:04d}{year}{serial:05d}"
        case_no = f"{year}{serial:05d}"

        gravity = "Heinous" if crime_type in HEINOUS_CRIME_TYPES else "Non-Heinous"
        days_since = (end - date_occurred).days
        status = _sample_status(rng, days_since)
        police_person_id = rng.choice(ref.employees_by_district[key])
        court_id = rng.choice(ref.courts_by_district[key])

        cur.execute(
            """INSERT INTO CaseMaster (CrimeNo, CaseNo, CrimeRegisteredDate, PolicePersonID, PoliceStationID,
               CaseCategoryID, GravityOffenceID, CrimeMajorHeadID, CrimeMinorHeadID, CaseStatusID, CourtID)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (crime_no, case_no, date_reported.isoformat(), police_person_id, unit_id,
             ref.case_category_id[category], ref.gravity_id[gravity], ref.crime_head_id[crime_type],
             ref.crime_subhead_id[crime_type], ref.case_status_id[status], court_id),
        )
        case_id = cur.lastrowid

        # --- Victim (and, for most crime types, the complainant is the victim) ---
        victim_can_self_report = crime_type not in DEATH_RELATED_TYPES
        v_gender = rng.choice(["M", "F"])
        v_first = rng.choice(MALE_FIRST_NAMES if v_gender == "M" else FEMALE_FIRST_NAMES)
        v_name = f"{v_first} {rng.choice(SURNAMES)}"
        v_age = rng.randint(5, 80)
        victim_police = "1" if rng.random() < 0.01 else "0"
        cur.execute(
            "INSERT INTO Victim (CaseMasterID, VictimName, AgeYear, GenderID, VictimPolice) VALUES (?, ?, ?, ?, ?)",
            (case_id, v_name, v_age, ref.gender_id[v_gender], victim_police),
        )

        if victim_can_self_report:
            c_name, c_age, c_gender = v_name, v_age, v_gender
        else:
            c_gender = rng.choice(["M", "F"])
            c_first = rng.choice(MALE_FIRST_NAMES if c_gender == "M" else FEMALE_FIRST_NAMES)
            c_name = f"{c_first} {rng.choice(SURNAMES)}"
            c_age = rng.randint(20, 70)

        occupation = rng.choice(all_occupations)
        religion = _weighted(rng, RELIGIONS, [0.70, 0.13, 0.05, 0.03, 0.02, 0.005, 0.03, 0.035])
        caste = _weighted(rng, CASTE_CATEGORIES, [0.50, 0.35, 0.11, 0.04])
        cur.execute(
            """INSERT INTO ComplainantDetails (CaseMasterID, ComplainantName, AgeYear, OccupationID, ReligionID, CasteID, GenderID)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, c_name, c_age, ref.occupation_id[occupation], ref.religion_id[religion],
             ref.caste_id[caste], ref.gender_id[c_gender]),
        )

        # --- Act/Section ------------------------------------------------------
        section_code = ref.section_code[crime_type]
        cur.execute(
            "INSERT INTO ActSectionAssociation (CaseMasterID, ActID, SectionID, ActOrderID, SectionOrderID) VALUES (?, ?, ?, 1, 1)",
            (case_id, ref.act_code, section_code),
        )

        # --- Accused ------------------------------------------------------------
        n_accused = _weighted(rng, N_ACCUSED_OPTIONS, N_ACCUSED_WEIGHTS)
        accused_people = accused_registry.group(key, n_accused, year)
        accused_ids = []
        relationship = None
        if crime_type in {"MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "KIDNAPPING_ABDUCTION",
                           "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY", "CRUELTY_BY_HUSBAND_RELATIVES"}:
            relationship = _weighted(rng, rel_types, rel_w)

        for i, person in enumerate(accused_people, start=1):
            cur.execute(
                "INSERT INTO Accused (CaseMasterID, AccusedName, AgeYear, GenderID, PersonID) VALUES (?, ?, ?, ?, ?)",
                (case_id, person["name"], person["age"], ref.gender_id[person["gender"]], f"A{i}"),
            )
            accused_ids.append(cur.lastrowid)

        # --- ArrestSurrender: not every accused is caught -----------------------
        arrest_rate = {"UNDER_INVESTIGATION": 0.25, "CHARGESHEETED": 0.85, "TRIAL": 0.9,
                        "CONVICTED": 0.95, "ACQUITTED": 0.9, "CLOSED": 0.15}[status]
        for accused_id in accused_ids:
            if rng.random() >= arrest_rate:
                continue
            arrest_type = "Arrest" if rng.random() < 0.85 else "Voluntary Surrender"
            arrest_date = min(date_reported + timedelta(days=rng.randint(0, 60)), end)
            io_id = rng.choice(ref.employees_by_district[key])
            cur.execute(
                """INSERT INTO ArrestSurrender (CaseMasterID, ArrestSurrenderTypeID, ArrestSurrenderDate,
                   ArrestSurrenderStateId, ArrestSurrenderDistrictId, PoliceStationID, IOID, CourtID,
                   AccusedMasterID, IsAccused, IsComplainantAccused) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)""",
                (case_id, ref.arrest_type_id[arrest_type], arrest_date.isoformat(),
                 ref.state_id[d["state"]], district_id, unit_id, io_id, court_id, accused_id),
            )
            arrest_surrender_id = cur.lastrowid
            cur.execute(
                "INSERT INTO inv_arrestsurrenderaccused (ArrestSurrenderID, AccusedMasterID) VALUES (?, ?)",
                (arrest_surrender_id, accused_id),
            )

        # --- ChargesheetDetails --------------------------------------------------
        if status in {"CHARGESHEETED", "TRIAL", "CONVICTED", "ACQUITTED"}:
            cstype = "A"
        elif status == "CLOSED":
            cstype = _weighted(rng, ["B", "C"], [0.3, 0.7])
        else:
            cstype = None
        if cstype:
            cs_date = min(date_reported + timedelta(days=rng.randint(30, 180)), end)
            cur.execute(
                "INSERT INTO ChargesheetDetails (CaseMasterID, csdate, cstype, PolicePersonID) VALUES (?, ?, ?, ?)",
                (case_id, cs_date.isoformat(), cstype, police_person_id),
            )

        # --- Inv_OccuranceTime (incident time/location/brief facts) --------------
        lat, lon, _precise = get_coordinates(d["state"], d["district"])
        accused_desc = relationship.lower() if relationship and relationship != "STRANGER" else "an unidentified person"
        brief_facts = DESCRIPTION_TEMPLATES[crime_type].format(
            victim=v_name, location=f"{d['district']}, {d['state']}", accused_desc=accused_desc,
        )
        cur.execute(
            """INSERT INTO Inv_OccuranceTime (CaseMasterID, IncidentFromDate, IncidentToDate, InfoReceivedPSDate,
               latitude, longitude, BriefFacts) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, f"{date_occurred.isoformat()} {_random_time(rng)}", f"{date_occurred.isoformat()} {_random_time(rng)}",
             f"{date_reported.isoformat()} {_random_time(rng)}", lat, lon, brief_facts),
        )

    conn.commit()
