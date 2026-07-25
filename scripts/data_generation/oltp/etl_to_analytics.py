"""
ETL: flattens the normalized OLTP database (matching the real Karnataka
Police ER schema) into the analytics-layer CSVs that network-analysis and
pattern-analytics already consume (data/schemas/synthetic_fir_schema.md).

The interesting part of this script is entity resolution (resolve_accused_
identities): the real schema has NO table linking an accused person across
different CaseMaster rows - each Accused row is scoped to one case, with only
a name/age/gender captured fresh each time. So "is this the same repeat
offender as in that other case" has to be *reconstructed* from name +
demographic similarity, the same problem a real deployment would face. This
uses a lightweight difflib-based fuzzy match; a production system would want
something considerably more robust (phonetic matching, government ID
linkage where available, ML-based entity resolution) - documented as a real
open problem, not solved here.

Two structural findings surfaced by building this pipeline, both handled by
just leaving the corresponding analytics columns empty rather than
fabricating data that has no source:
  - weapon_used: the real ER schema has no weapon field anywhere.
  - property_value_inr: the real ER schema has no monetary-value field.
  - income_bracket / occupation on Accused/Victim: only ComplainantDetails
    carries OccupationID, and none of the three tables carry income - so
    these are only populated for complainant-derived person rows, and left
    blank elsewhere.

CasteID/ReligionID are read from ComplainantDetails during this ETL (to
confirm they don't leak into the entity-resolution key or anywhere else) but
are NEVER written into any analytics output column - the attribute
decoupling principle enforced structurally, not just documented.
"""
import csv
import sqlite3
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference_data import ACT_SECTION_MAP
from crime_type_profiles import NARRATIVE_TEMPLATES, STATUS_CLAUSE

ROOT = Path(__file__).resolve().parents[3]

SECTION_TO_CRIME_TYPE = {section: crime_type for crime_type, (_act, section, _desc) in ACT_SECTION_MAP.items()}

NAME_MATCH_THRESHOLD = 0.82
BIRTH_YEAR_TOLERANCE = 3


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def resolve_accused_identities(rows: list[dict]) -> dict[int, str]:
    """rows: AccusedMasterID, AccusedName, GenderID(code), district, AgeYear, case_year.
    Returns {AccusedMasterID: resolved_person_id}."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    resolved: dict[int, str] = {}
    counter = 0

    for row in sorted(rows, key=lambda r: r["case_year"]):
        bucket_key = (row["gender"], row["district"])
        clusters = buckets[bucket_key]
        norm_name = _normalize_name(row["name"])
        implied_birth_year = row["case_year"] - row["age"]

        match = None
        for cluster in clusters:
            if abs(cluster["birth_year"] - implied_birth_year) > BIRTH_YEAR_TOLERANCE:
                continue
            if SequenceMatcher(None, norm_name, cluster["rep_norm_name"]).ratio() >= NAME_MATCH_THRESHOLD:
                match = cluster
                break

        if match:
            match["members"].append(row["AccusedMasterID"])
            resolved[row["AccusedMasterID"]] = match["person_id"]
        else:
            counter += 1
            person_id = f"ACC-{counter:06d}"
            clusters.append({
                "rep_norm_name": norm_name, "birth_year": implied_birth_year,
                "members": [row["AccusedMasterID"]], "person_id": person_id,
                "display_name": row["name"],
            })
            resolved[row["AccusedMasterID"]] = person_id

    return resolved


def run_etl(db_path: Path, out_dir: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = cur.execute("""
        SELECT cm.CaseMasterID, cm.CrimeNo, cm.CrimeRegisteredDate, cm.CaseStatusID, csm.CaseStatusName,
               u.UnitName as police_station, d.DistrictName as district, st.StateName as state,
               io.IncidentFromDate, io.InfoReceivedPSDate, io.latitude, io.longitude, io.BriefFacts,
               asn.SectionID
        FROM CaseMaster cm
        JOIN Unit u ON cm.PoliceStationID = u.UnitID
        JOIN District d ON u.DistrictID = d.DistrictID
        JOIN State st ON d.StateID = st.StateID
        JOIN Inv_OccuranceTime io ON io.CaseMasterID = cm.CaseMasterID
        JOIN CaseStatusMaster csm ON cm.CaseStatusID = csm.CaseStatusID
        LEFT JOIN ActSectionAssociation asn ON asn.CaseMasterID = cm.CaseMasterID
    """).fetchall()

    victims = cur.execute("SELECT * FROM Victim").fetchall()
    victims_by_case = defaultdict(list)
    for v in victims:
        victims_by_case[v["CaseMasterID"]].append(v)

    accused_raw = cur.execute("""
        SELECT a.AccusedMasterID, a.CaseMasterID, a.AccusedName, a.AgeYear, g.GenderCode,
               d.DistrictName as district, cm.CrimeRegisteredDate
        FROM Accused a
        JOIN CaseMaster cm ON a.CaseMasterID = cm.CaseMasterID
        JOIN Unit u ON cm.PoliceStationID = u.UnitID
        JOIN District d ON u.DistrictID = d.DistrictID
        JOIN GenderMaster g ON a.GenderID = g.GenderID
    """).fetchall()
    accused_input = [
        {"AccusedMasterID": r["AccusedMasterID"], "name": r["AccusedName"], "gender": r["GenderCode"],
         "district": r["district"], "age": r["AgeYear"], "case_year": int(r["CrimeRegisteredDate"][:4])}
        for r in accused_raw
    ]
    resolved_accused = resolve_accused_identities(accused_input)
    accused_by_case = defaultdict(list)
    for r in accused_raw:
        accused_by_case[r["CaseMasterID"]].append(r)

    complainants = cur.execute("""
        SELECT cd.*, om.OccupationName
        FROM ComplainantDetails cd
        LEFT JOIN OccupationMaster om ON cd.OccupationID = om.OccupationID
    """).fetchall()
    complainants_by_case = defaultdict(list)
    for c in complainants:
        complainants_by_case[c["CaseMasterID"]].append(c)

    person_rows = {}
    fir_rows = []
    link_rows = []

    def ensure_person(person_id, name, gender_code, age, district, state, occupation=None):
        if person_id not in person_rows:
            person_rows[person_id] = {
                "person_id": person_id, "full_name": name, "gender": gender_code, "age": age,
                "address_district": district, "address_state": state,
                "occupation": occupation or "", "income_bracket": "",
            }

    victim_counter = 0
    complainant_counter = 0

    for case in cases:
        crime_type = SECTION_TO_CRIME_TYPE.get(case["SectionID"], "OTHER_IPC_CRIMES")
        date_occurred, time_occurred = case["IncidentFromDate"].split(" ")
        date_reported = case["CrimeRegisteredDate"]
        time_reported = case["InfoReceivedPSDate"].split(" ")[1] if case["InfoReceivedPSDate"] else "00:00:00"
        act_code, section_code, _desc = ACT_SECTION_MAP[crime_type]

        case_victims = victims_by_case.get(case["CaseMasterID"], [])
        primary_victim_name = case_victims[0]["VictimName"] if case_victims else "the complainant"
        primary_victim_age = case_victims[0]["AgeYear"] if case_victims else None

        case_accused = accused_by_case.get(case["CaseMasterID"], [])
        accused_names = [a["AccusedName"] for a in case_accused]
        if accused_names:
            who = accused_names[0] if len(accused_names) == 1 else f"{len(accused_names)} accused persons including {accused_names[0]}"
            accused_clause = f"The complainant has named {who}."
        else:
            accused_clause = "The identity of the accused is yet to be established."

        template = NARRATIVE_TEMPLATES.get(crime_type, NARRATIVE_TEMPLATES["DEFAULT"])
        narrative = template.format(
            date=date_occurred, time=time_occurred, police_station=case["police_station"],
            victim=primary_victim_name, victim_age=primary_victim_age if primary_victim_age is not None else "unknown",
            location=f"{case['district']}, {case['state']}", accused_clause=accused_clause,
            ipc_section=f"{section_code} {act_code}", status_clause=STATUS_CLAUSE[case["CaseStatusName"]],
            property_value="an undisclosed amount",
        )

        fir_rows.append({
            "fir_id": case["CrimeNo"], "state": case["state"], "district": case["district"],
            "police_station": case["police_station"], "lat": case["latitude"], "lon": case["longitude"],
            "geo_precise": "",  # recomputed below in bulk, see note in build script
            "date_reported": date_reported, "time_reported": time_reported,
            "date_occurred": date_occurred, "time_occurred": time_occurred,
            "crime_type_code": crime_type, "ipc_section": f"{section_code} {act_code}",
            "crime_description": case["BriefFacts"], "narrative": narrative,
            "weapon_used": "",       # not captured anywhere in the real ER schema - see module docstring
            "property_value_inr": "",  # not captured anywhere in the real ER schema - see module docstring
            "status": case["CaseStatusName"],
        })

        for v in case_victims:
            victim_counter += 1
            pid = f"VIC-{victim_counter:06d}"
            ensure_person(pid, v["VictimName"], _gender_code(cur, v["GenderID"]), v["AgeYear"],
                          case["district"], case["state"])
            link_rows.append({"fir_id": case["CrimeNo"], "person_id": pid, "role": "VICTIM", "relationship_to_victim": ""})

        for c in complainants_by_case.get(case["CaseMasterID"], []):
            complainant_counter += 1
            pid = f"CMP-{complainant_counter:06d}"
            gender_code = _gender_code(cur, c["GenderID"])
            # CasteID / ReligionID are read here only to confirm they exist upstream -
            # neither is written into person_rows or anywhere else. See module docstring.
            ensure_person(pid, c["ComplainantName"], gender_code, c["AgeYear"], case["district"], case["state"],
                          occupation=c["OccupationName"])
            link_rows.append({"fir_id": case["CrimeNo"], "person_id": pid, "role": "COMPLAINANT", "relationship_to_victim": ""})

        for a in case_accused:
            pid = resolved_accused[a["AccusedMasterID"]]
            ensure_person(pid, a["AccusedName"], a["GenderCode"], a["AgeYear"], case["district"], case["state"])
            link_rows.append({"fir_id": case["CrimeNo"], "person_id": pid, "role": "ACCUSED", "relationship_to_victim": ""})

    conn.close()
    return person_rows, fir_rows, link_rows


_gender_code_cache = {}


def _gender_code(cur, gender_id):
    if gender_id not in _gender_code_cache:
        row = cur.execute("SELECT GenderCode FROM GenderMaster WHERE GenderID = ?", (gender_id,)).fetchone()
        _gender_code_cache[gender_id] = row["GenderCode"] if row else "M"
    return _gender_code_cache[gender_id]
