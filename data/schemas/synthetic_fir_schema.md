# Synthetic FIR Dataset — Entity Schema

Everything here is **synthetic** (names, IDs, narratives). The parts that are
**calibrated against real NCRB data** are: crime-type mix, district/geographic
distribution, and accused-victim relationship mix. See
`scripts/data_generation/calibrate_ncrb.py` and `data/processed/calibration/`
for the calibration source and methodology, and `data/raw/MANIFEST.md` for
dataset provenance.

**Provenance as of this version:** these CSVs are no longer generated
directly — they're the ETL output of a normalized OLTP database matching
the real Karnataka Police Department FIR system schema
(`docs/architecture/Police_FIR_ER_Diagram.pdf`). See
`scripts/data_generation/oltp/README.md` for the pipeline, and in particular
for the entity-resolution approach (repeat offenders are *reconstructed*
from name/demographic similarity, since the real schema has no cross-case
person identity) and a list of fields the real schema doesn't actually
capture (`weapon_used`, `property_value_inr`, witness role) that are now
consequently blank/absent here rather than fabricated. `fir_id` is now the
real `CrimeNo` format (e.g. `103541451202000002`), not a `FIR-YYYY-NNNNNN`
placeholder.

## `person.csv`
One row per synthetic individual. A person can appear as ACCUSED in one FIR
and WITNESS in another — role is per-link, not per-person (see
`fir_person_link.csv`), so repeat offenders and recurring witnesses are
representable.

| Field | Type | Notes |
|---|---|---|
| `person_id` | string (PK) | `P-000001` style |
| `full_name` | string | synthetic, sampled from curated Indian name pools |
| `gender` | enum | M / F |
| `age` | int | |
| `address_state` | string | |
| `address_district` | string | |
| `occupation` | string | |
| `income_bracket` | enum | LOW / LOWER_MIDDLE / MIDDLE / UPPER_MIDDLE / HIGH — synthetic, drives the sociological-correlation demo (pillar 4), not derived from a real individual-level source |

## `fir.csv`
One row per case.

| Field | Type | Notes |
|---|---|---|
| `fir_id` | string (PK) | `FIR-2018-000001` style |
| `state` | string | |
| `district` | string | |
| `police_station` | string | synthetic |
| `lat`, `lon` | float | see `geo_lookup.py` — `geo_precise=True` districts have real coordinates, `False` districts are jittered around the state capital |
| `geo_precise` | bool | |
| `date_reported`, `time_reported` | date / time | |
| `date_occurred`, `time_occurred` | date / time | occurred <= reported |
| `crime_type_code` | string | one of the 21 NCRB-derived categories in `crime_type_mix.json` |
| `crime_description` | string | short templated line |
| `narrative` | string | longer FIR-style templated paragraph — for the NLP/summarization/chatbot demo |
| `weapon_used` | string \| null | |
| `property_value_inr` | float \| null | only for THEFT / BURGLARY / ROBBERY / DACOITY / AUTO_THEFT |
| `status` | enum | UNDER_INVESTIGATION / CHARGESHEETED / TRIAL / CONVICTED / ACQUITTED / CLOSED |

## `fir_person_link.csv`
Many-to-many: which people are attached to which case, and how.

| Field | Type | Notes |
|---|---|---|
| `fir_id` | string (FK) | |
| `person_id` | string (FK) | |
| `role` | enum | ACCUSED / VICTIM / WITNESS / COMPLAINANT |
| `relationship_to_victim` | enum \| null | STRANGER / NEIGHBOR / ACQUAINTANCE / FAMILY / RELATIVE — only set on ACCUSED rows, sampled from `offender_relationship_mix.json` |

## `network_edge.csv`
Co-offending / associate graph — the input to the criminal-network-analysis
pillar (pillar 2). Generated from `fir_person_link.csv`: any two ACCUSED
persons linked to the same FIR get an edge.

| Field | Type | Notes |
|---|---|---|
| `person_id_a`, `person_id_b` | string (FK) | `a < b` lexicographically, no duplicate/reverse edges |
| `edge_type` | enum | CO_ACCUSED (only type generated in v1) |
| `shared_fir_count` | int | number of cases both were accused together in |
| `fir_ids` | string | pipe-separated list of shared FIR IDs, for evidence-trail/explainability drill-down |

## `offender_profile.csv`
One row per person who appears as ACCUSED at least once — a light rollup,
not a trained risk model. `risk_tier` is a transparent rule-based placeholder
(prior case count + weapon-use flag), explicitly NOT a calibrated prediction —
the real risk-scoring model (pillar 5) trains on this data later, on Kaggle,
and replaces this column.

| Field | Type | Notes |
|---|---|---|
| `person_id` | string (FK) | |
| `prior_case_count` | int | count of FIRs where this person is ACCUSED |
| `distinct_crime_types` | string | pipe-separated list |
| `used_weapon_ever` | bool | |
| `risk_tier` | enum | LOW / MEDIUM / HIGH — rule-based placeholder, see note above |

## Known limitations (by design, for a demo-grade dataset)
- Temporal micro-patterns (hour-of-day, day-of-week, seasonality) are
  criminology-informed heuristics, not calibrated from real NCRB data — the
  raw files here are annual aggregates with no timestamp granularity.
- `geo_precise=False` districts (~69% of crime-weight, the long tail of
  lower-volume districts) get a deterministic jittered offset from their
  state capital, not a real geocode — good enough for hotspot clustering demos,
  not for claims about a specific fallback district's coordinates.
- Individual-level fields (names, ages, narratives) are entirely synthetic;
  only the aggregate distributions they're sampled from are real.
