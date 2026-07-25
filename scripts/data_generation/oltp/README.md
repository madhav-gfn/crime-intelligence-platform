# OLTP Schema + ETL Pipeline

Generates synthetic case data matching the **real Karnataka Police
Department FIR system schema**
(`docs/architecture/Police_FIR_ER_Diagram.pdf` — confidential, internal
reference only), then flattens it into the analytics-layer CSVs that
`backend/services/network-analysis` and `backend/services/pattern-analytics`
consume. This replaced the earlier flat generator
(`scripts/data_generation/generate_synthetic_fir_data.py`) as the source of
`data/seed/*.csv` — that script still exists and still runs, but its output
is no longer what the services read.

## Pipeline

```
database/migrations/*.sql          -- DDL matching the real ER diagram
        |
        v
oltp/reference_data.py             -- lookup/master tables (State, District,
        |                              Unit hierarchy, Rank, Act/Section, ...)
        v
oltp/build_database.py             -- orchestrates the above into a SQLite DB
        |                              (data/processed/fir_system_oltp.sqlite)
        v
oltp/transactional_data.py         -- CaseMaster + children, calibrated
        |                              against the same NCRB distributions
        |                              as the flat generator
        v
oltp/etl_to_analytics.py           -- entity resolution + flatten to CSVs
        |
        v
oltp/write_analytics_csvs.py       -- writes data/seed/*.csv
```

Run it end to end:
```bash
python scripts/data_generation/oltp/build_database.py --n-cases 5000 --seed 42
python scripts/data_generation/oltp/write_analytics_csvs.py
```

## The interesting part: entity resolution

The real schema has **no table linking an accused person across different
`CaseMaster` rows** — `Accused.AccusedMasterID` is scoped to one case, with
only a name/age/gender captured fresh each time. There's no `PersonID`
master table for accused persons at all. That means a real deployment
genuinely cannot tell "is this the same repeat offender as in that other
case" from a foreign key — it has to be *reconstructed* from name and
demographic similarity, which is exactly the transliteration/spelling-drift
problem the platform's own research doc (`Conversational Crime Analytics AI
Research.md`) flags as a real regional-data-quality issue.

`transactional_data.py` models this honestly: it tracks a "true" offender
identity internally (to decide which cases a repeat offender shows up in,
with age drifting realistically over time and a 15% chance of spelling
drift on each reuse), but never writes that identity anywhere — each
appearance is an independent `Accused` row, same as the real schema would
produce. `etl_to_analytics.py`'s `resolve_accused_identities()` then has to
*rediscover* the links using a difflib fuzzy-name-match (threshold 0.82)
gated by same gender + district + a ±3 year birth-year tolerance. On the
5,000-case dataset this resolves 8,675 accused case-appearances down to
4,746 distinct persons — 3,929 repeat-offender re-links recovered from
nothing but name and demographic similarity.

This is a real, imperfect heuristic, not a solved problem — a production
system would want phonetic matching, government ID linkage where available,
or an ML-based entity-resolution model. The point of building it this way
is that the gap is now a documented, demonstrable part of the pipeline
instead of an assumption hidden inside a synthetic dataset.

## Real schema gaps this build surfaced

Building against the actual ER diagram (rather than inventing a schema)
surfaced several fields the earlier synthetic dataset had that **the real
system doesn't actually capture**:

| Field | Status |
|---|---|
| `weapon_used` | Not in the schema anywhere. Left blank in `fir.csv`. Any real weapon signal would have to come from NLP over `BriefFacts` free text, not a structured column. |
| `property_value_inr` | Not in the schema anywhere. Left blank. |
| Witness role | No `Witness` table exists — only `Victim`, `Accused`, `ComplainantDetails`. Witnesses aren't structurally modeled in this system (likely captured in unstructured statements outside this ER export). Dropped from `fir_person_link.csv`. |
| `occupation` / income | Only `ComplainantDetails.OccupationID` exists — `Victim` and `Accused` carry no occupation or income field at all. `person.csv` only has non-empty `occupation` for `COMPLAINANT`-role rows. |
| Cross-case person identity | Doesn't exist — see entity resolution above. |

`pattern-analytics`'s MO-similarity feature (`weapon_used`) and district
severity's `avg_property_value_inr` both degrade gracefully to fewer
signal dimensions rather than erroring — but this is worth knowing before
presenting either as a finished capability.

## Attribute decoupling, enforced structurally

`ComplainantDetails.CasteID` / `ReligionID` are read during ETL only to
confirm they exist upstream — **neither is ever written into any analytics
output column**. This isn't just a policy note: `etl_to_analytics.py`'s
`ensure_person()` function has no caste/religion parameter, so there's no
code path that could leak them into `person.csv` even by mistake. That's
the platform's fairness/attribute-decoupling principle (see the COMPAS
discussion in the research doc) enforced by the shape of the code, not just
documented as a rule to follow.
