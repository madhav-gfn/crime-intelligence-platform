"""
Populates every lookup/master/organizational table from
database/migrations/001_lookup_and_org_tables.sql: State, District, Unit
hierarchy, Rank, Designation, Employee, Court, CaseCategory, GravityOffence,
CrimeHead/CrimeSubHead, Act/Section, CasteMaster, ReligionMaster,
OccupationMaster, CaseStatusMaster.

A note on CasteMaster: the real ER schema tracks caste on ComplainantDetails.
This exists for a real, legally-grounded reason - the SC/ST (Prevention of
Atrocities) Act and welfare-scheme eligibility tracking require it, and NCRB
itself publishes SC/ST crime statistics (see data/raw/MANIFEST.md, the
rajanand-crime-in-india district-wise SC/ST files). This generator only
populates the four constitutional protection categories (General/OBC/SC/ST),
not granular sub-caste - and critically, oltp/etl.py never selects CasteID or
ReligionID into the analytics-layer output at all. That's the attribute
decoupling principle from the platform's fairness/governance design applied
structurally, not just as a policy note.
"""
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from name_pools import FEMALE_FIRST_NAMES, MALE_FIRST_NAMES, OCCUPATIONS_BY_INCOME, SURNAMES

RANKS = [
    ("Director General of Police", 1), ("Additional DGP", 2), ("Inspector General of Police", 3),
    ("Deputy Inspector General of Police", 4), ("Superintendent of Police", 5),
    ("Additional Superintendent of Police", 6), ("Deputy Superintendent of Police", 7),
    ("Police Inspector", 8), ("Sub-Inspector", 9), ("Assistant Sub-Inspector", 10),
    ("Head Constable", 11), ("Police Constable", 12),
]

DESIGNATIONS = [
    ("Investigating Officer", 1), ("Station House Officer", 2), ("Case Officer", 3),
    ("Beat Officer", 4), ("Records Officer", 5),
]

GENDERS = [("M", "Male"), ("F", "Female"), ("T", "Transgender")]

UNIT_TYPES = [
    ("State Headquarters", "State", 1),
    ("District Headquarters", "District", 2),
    ("Police Station", "City", 3),
]

CASE_CATEGORIES = [("FIR", "1"), ("UDR", "3"), ("PAR", "4"), ("Zero FIR", "8")]

GRAVITY_OFFENCES = ["Heinous", "Non-Heinous"]
HEINOUS_CRIME_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY", "KIDNAPPING_ABDUCTION",
    "DOWRY_DEATH", "ROBBERY",
}

# crime_type_code -> (crime_head, crime_subhead_display_name)
CRIME_HEAD_MAP = {
    "MURDER": ("Crimes Against Body", "Murder"),
    "ATTEMPT_TO_MURDER": ("Crimes Against Body", "Attempt to Murder"),
    "CULPABLE_HOMICIDE": ("Crimes Against Body", "Culpable Homicide"),
    "HURT_GRIEVOUS_HURT": ("Crimes Against Body", "Hurt / Grievous Hurt"),
    "RIOTS": ("Crimes Against Body", "Riots"),
    "RAPE": ("Crimes Against Women", "Rape"),
    "DOWRY_DEATH": ("Crimes Against Women", "Dowry Death"),
    "ASSAULT_ON_WOMEN_MODESTY": ("Crimes Against Women", "Assault on Women - Outraging Modesty"),
    "CRUELTY_BY_HUSBAND_RELATIVES": ("Crimes Against Women", "Cruelty by Husband or Relatives"),
    "KIDNAPPING_ABDUCTION": ("Crimes Against Women", "Kidnapping & Abduction"),
    "DACOITY": ("Crimes Against Property", "Dacoity"),
    "ROBBERY": ("Crimes Against Property", "Robbery"),
    "BURGLARY": ("Crimes Against Property", "Burglary"),
    "THEFT": ("Crimes Against Property", "Theft"),
    "AUTO_THEFT": ("Crimes Against Property", "Motor Vehicle Theft"),
    "OTHER_THEFT": ("Crimes Against Property", "Other Theft"),
    "ARSON": ("Crimes Against Property", "Arson"),
    "CRIMINAL_BREACH_OF_TRUST": ("Crimes Against Property", "Criminal Breach of Trust"),
    "CHEATING": ("Economic Offences", "Cheating"),
    "DEATH_BY_NEGLIGENCE": ("Other IPC Crimes", "Causing Death by Negligence"),
    "OTHER_IPC_CRIMES": ("Other IPC Crimes", "Other IPC Crimes"),
}

# crime_type_code -> (act_code, section_code, section_description). Primary
# section only where the source mapping listed multiple (e.g. BURGLARY was
# "457/380 IPC" in crime_type_profiles.py) - documented simplification.
ACT_SECTION_MAP = {
    "MURDER": ("IPC", "302", "Punishment for murder"),
    "ATTEMPT_TO_MURDER": ("IPC", "307", "Attempt to murder"),
    "CULPABLE_HOMICIDE": ("IPC", "304", "Culpable homicide not amounting to murder"),
    "RAPE": ("IPC", "376", "Punishment for rape"),
    "KIDNAPPING_ABDUCTION": ("IPC", "363", "Punishment for kidnapping"),
    "DACOITY": ("IPC", "395", "Punishment for dacoity"),
    "ROBBERY": ("IPC", "392", "Punishment for robbery"),
    "BURGLARY": ("IPC", "457", "Lurking house-trespass by night to commit an offence"),
    "THEFT": ("IPC", "379", "Punishment for theft"),
    "AUTO_THEFT": ("IPC", "379A", "Theft of motor vehicle"),
    "OTHER_THEFT": ("IPC", "379B", "Theft - other property"),
    "RIOTS": ("IPC", "147", "Punishment for rioting"),
    "CRIMINAL_BREACH_OF_TRUST": ("IPC", "406", "Punishment for criminal breach of trust"),
    "CHEATING": ("IPC", "420", "Cheating and dishonestly inducing delivery of property"),
    "ARSON": ("IPC", "435", "Mischief by fire or explosive substance"),
    "HURT_GRIEVOUS_HURT": ("IPC", "325", "Punishment for voluntarily causing grievous hurt"),
    "DOWRY_DEATH": ("IPC", "304B", "Dowry death"),
    "ASSAULT_ON_WOMEN_MODESTY": ("IPC", "354", "Assault or use of criminal force with intent to outrage modesty"),
    "CRUELTY_BY_HUSBAND_RELATIVES": ("IPC", "498A", "Cruelty by husband or relatives of husband"),
    "DEATH_BY_NEGLIGENCE": ("IPC", "304A", "Causing death by negligence"),
    "OTHER_IPC_CRIMES": ("IPC", "OTH", "Other IPC sections"),
}

CASTE_CATEGORIES = ["General", "OBC", "SC", "ST"]
RELIGIONS = ["Hindu", "Muslim", "Christian", "Sikh", "Buddhist", "Jain", "Other", "Not Stated"]
CASE_STATUSES = ["UNDER_INVESTIGATION", "CHARGESHEETED", "TRIAL", "CONVICTED", "ACQUITTED", "CLOSED"]
ARREST_SURRENDER_TYPES = ["Arrest", "Voluntary Surrender"]

POLICE_STATIONS_PER_DISTRICT = 3
EMPLOYEES_PER_DISTRICT = 5


class RefData:
    """Bundles every id-map the transactional generator needs."""

    def __init__(self):
        self.state_id: dict[str, int] = {}
        self.district_id: dict[tuple[str, str], int] = {}
        self.ps_units_by_district: dict[tuple[str, str], list[int]] = {}
        self.district_hq_unit: dict[tuple[str, str], int] = {}
        self.employees_by_district: dict[tuple[str, str], list[int]] = {}
        self.courts_by_district: dict[tuple[str, str], list[int]] = {}
        self.rank_id: dict[str, int] = {}
        self.designation_id: dict[str, int] = {}
        self.gender_id: dict[str, int] = {}
        self.case_category_id: dict[str, int] = {}
        self.gravity_id: dict[str, int] = {}
        self.crime_head_id: dict[str, int] = {}
        self.crime_subhead_id: dict[str, int] = {}  # keyed by crime_type_code
        self.act_code = "IPC"
        self.section_code: dict[str, str] = {}  # keyed by crime_type_code
        self.caste_id: dict[str, int] = {}
        self.religion_id: dict[str, int] = {}
        self.occupation_id: dict[str, int] = {}
        self.case_status_id: dict[str, int] = {}
        self.arrest_type_id: dict[str, int] = {}


def load_reference_data(conn: sqlite3.Connection, district_weights: list[dict], rng: random.Random) -> RefData:
    ref = RefData()
    cur = conn.cursor()

    # --- States & Districts -------------------------------------------------
    states = sorted({d["state"] for d in district_weights})
    for state in states:
        cur.execute("INSERT INTO State (StateName) VALUES (?)", (state,))
        ref.state_id[state] = cur.lastrowid

    for d in district_weights:
        key = (d["state"], d["district"])
        cur.execute(
            "INSERT INTO District (DistrictName, StateID) VALUES (?, ?)",
            (d["district"], ref.state_id[d["state"]]),
        )
        ref.district_id[key] = cur.lastrowid

    # --- Unit hierarchy: State HQ -> District HQ -> Police Stations --------
    unit_type_id = {}
    for name, level, hierarchy in UNIT_TYPES:
        cur.execute("INSERT INTO UnitType (UnitTypeName, CityDistState, Hierarchy) VALUES (?, ?, ?)", (name, level, hierarchy))
        unit_type_id[name] = cur.lastrowid

    state_hq_unit = {}
    for state, sid in ref.state_id.items():
        cur.execute(
            "INSERT INTO Unit (UnitName, TypeID, StateID) VALUES (?, ?, ?)",
            (f"{state.title()} State Police HQ", unit_type_id["State Headquarters"], sid),
        )
        state_hq_unit[state] = cur.lastrowid

    for d in district_weights:
        key = (d["state"], d["district"])
        did = ref.district_id[key]
        sid = ref.state_id[d["state"]]
        cur.execute(
            "INSERT INTO Unit (UnitName, TypeID, ParentUnit, StateID, DistrictID) VALUES (?, ?, ?, ?, ?)",
            (f"{d['district'].title()} District Police HQ", unit_type_id["District Headquarters"],
             state_hq_unit[d["state"]], sid, did),
        )
        district_hq = cur.lastrowid
        ref.district_hq_unit[key] = district_hq

        ps_ids = []
        for i in range(POLICE_STATIONS_PER_DISTRICT):
            cur.execute(
                "INSERT INTO Unit (UnitName, TypeID, ParentUnit, StateID, DistrictID) VALUES (?, ?, ?, ?, ?)",
                (f"{d['district'].title()} PS-{i + 1}", unit_type_id["Police Station"], district_hq, sid, did),
            )
            ps_ids.append(cur.lastrowid)
        ref.ps_units_by_district[key] = ps_ids

    # --- Rank / Designation / Gender ----------------------------------------
    for name, hierarchy in RANKS:
        cur.execute("INSERT INTO Rank (RankName, Hierarchy) VALUES (?, ?)", (name, hierarchy))
        ref.rank_id[name] = cur.lastrowid

    for name, sort_order in DESIGNATIONS:
        cur.execute("INSERT INTO Designation (DesignationName, SortOrder) VALUES (?, ?)", (name, sort_order))
        ref.designation_id[name] = cur.lastrowid

    for code, name in GENDERS:
        cur.execute("INSERT INTO GenderMaster (GenderCode, GenderName) VALUES (?, ?)", (code, name))
        ref.gender_id[code] = cur.lastrowid

    # --- Employees: a handful of officers per district, spread across ranks -
    investigator_ranks = ["Police Inspector", "Sub-Inspector", "Assistant Sub-Inspector", "Head Constable"]
    kgid_counter = 0
    for d in district_weights:
        key = (d["state"], d["district"])
        emp_ids = []
        for _ in range(EMPLOYEES_PER_DISTRICT):
            kgid_counter += 1
            gender = rng.choice(["M", "F"])
            first = rng.choice(MALE_FIRST_NAMES if gender == "M" else FEMALE_FIRST_NAMES)
            last = rng.choice(SURNAMES)
            rank_name = rng.choice(investigator_ranks)
            designation_name = rng.choice([n for n, _ in DESIGNATIONS])
            unit_id = rng.choice(ref.ps_units_by_district[key])
            cur.execute(
                """INSERT INTO Employee (DistrictID, UnitID, RankID, DesignationID, KGID, FirstName, GenderID)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ref.district_id[key], unit_id, ref.rank_id[rank_name], ref.designation_id[designation_name],
                 f"KGID-{kgid_counter:06d}", f"{first} {last}", ref.gender_id[gender]),
            )
            emp_ids.append(cur.lastrowid)
        ref.employees_by_district[key] = emp_ids

    # --- Courts: one district & sessions court per district -----------------
    for d in district_weights:
        key = (d["state"], d["district"])
        court_ids = []
        for court_name in [f"{d['district'].title()} District & Sessions Court", f"{d['district'].title()} JMFC Court"]:
            cur.execute(
                "INSERT INTO Court (CourtName, DistrictID, StateID) VALUES (?, ?, ?)",
                (court_name, ref.district_id[key], ref.state_id[d["state"]]),
            )
            court_ids.append(cur.lastrowid)
        ref.courts_by_district[key] = court_ids

    # --- CaseCategory / GravityOffence ---------------------------------------
    for name, _prefix in CASE_CATEGORIES:
        cur.execute("INSERT INTO CaseCategory (LookupValue) VALUES (?)", (name,))
        ref.case_category_id[name] = cur.lastrowid

    for name in GRAVITY_OFFENCES:
        cur.execute("INSERT INTO GravityOffence (LookupValue) VALUES (?)", (name,))
        ref.gravity_id[name] = cur.lastrowid

    # --- CrimeHead / CrimeSubHead --------------------------------------------
    seen_heads = {}
    for crime_type, (head_name, subhead_name) in CRIME_HEAD_MAP.items():
        if head_name not in seen_heads:
            cur.execute("INSERT INTO CrimeHead (CrimeGroupName) VALUES (?)", (head_name,))
            seen_heads[head_name] = cur.lastrowid
        ref.crime_head_id[crime_type] = seen_heads[head_name]
        cur.execute(
            "INSERT INTO CrimeSubHead (CrimeHeadID, CrimeHeadName) VALUES (?, ?)",
            (seen_heads[head_name], subhead_name),
        )
        ref.crime_subhead_id[crime_type] = cur.lastrowid

    # --- Act / Section / CrimeHeadActSection --------------------------------
    cur.execute("INSERT INTO Act (ActCode, ActDescription, ShortName) VALUES (?, ?, ?)",
                ("IPC", "Indian Penal Code", "IPC"))
    inserted_sections = set()
    for crime_type, (act_code, section_code, description) in ACT_SECTION_MAP.items():
        if section_code not in inserted_sections:
            cur.execute(
                "INSERT INTO Section (SectionCode, ActCode, SectionDescription) VALUES (?, ?, ?)",
                (section_code, act_code, description),
            )
            inserted_sections.add(section_code)
        ref.section_code[crime_type] = section_code
        cur.execute(
            "INSERT OR IGNORE INTO CrimeHeadActSection (CrimeHeadID, ActCode, SectionCode) VALUES (?, ?, ?)",
            (ref.crime_head_id[crime_type], act_code, section_code),
        )

    # --- CasteMaster / ReligionMaster / OccupationMaster ---------------------
    for name in CASTE_CATEGORIES:
        cur.execute("INSERT INTO CasteMaster (caste_master_name) VALUES (?)", (name,))
        ref.caste_id[name] = cur.lastrowid

    for name in RELIGIONS:
        cur.execute("INSERT INTO ReligionMaster (ReligionName) VALUES (?)", (name,))
        ref.religion_id[name] = cur.lastrowid

    all_occupations = sorted({occ for occs in OCCUPATIONS_BY_INCOME.values() for occ in occs})
    for name in all_occupations:
        cur.execute("INSERT INTO OccupationMaster (OccupationName) VALUES (?)", (name,))
        ref.occupation_id[name] = cur.lastrowid

    # --- CaseStatusMaster / ArrestSurrenderTypeMaster -------------------------
    for name in CASE_STATUSES:
        cur.execute("INSERT INTO CaseStatusMaster (CaseStatusName) VALUES (?)", (name,))
        ref.case_status_id[name] = cur.lastrowid

    for name in ARREST_SURRENDER_TYPES:
        cur.execute("INSERT INTO ArrestSurrenderTypeMaster (TypeName) VALUES (?)", (name,))
        ref.arrest_type_id[name] = cur.lastrowid

    conn.commit()
    return ref
