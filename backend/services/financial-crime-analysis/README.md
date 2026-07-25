# financial-crime-analysis

Financial crime / transaction analysis (pillar 7). The odd one out among the
four services: this one runs entirely on **real transaction data with real
ground-truth labels** — the IBM AML benchmark dataset (`data/raw/aml-ibm/`,
HI-Small variant, CDLA-Sharing-1.0 license, see `data/raw/MANIFEST.md`) —
not NCRB-calibrated synthetic FIRs. 5,078,345 transactions, 515,080
accounts, 5,177 labeled laundering transactions across 6,357 accounts, plus
370 hand-labeled example laundering structures (`HI-Small_Patterns.txt`)
covering 8 typologies (FAN-OUT, FAN-IN, CYCLE, GATHER-SCATTER,
SCATTER-GATHER, STACK, BIPARTITE, RANDOM).

Because there's real ground truth, this is the one pillar where "does the
analytics actually work" can be answered with a number instead of a
plausibility argument — see **Evaluation** below, and don't skip it before
presenting this service as a finished detector.

## Data pipeline

```
data/raw/aml-ibm/HI-Small_{Trans,accounts,Patterns}.{csv,txt}
                        |
                        v
scripts/data_generation/financial_crime/build_transaction_graph.py
   - per-account aggregation: out/in amount, count, degree, distinct
     currencies, max single transaction
   - 5 rule flags, thresholds derived from the ACTUAL data distribution
     (99th percentile fan-out/fan-in degree, 98th percentile transaction
     value) rather than guessed constants
   - risk_score / risk_tier (LOW/MEDIUM/HIGH) per account
   - evaluates the rule engine against the real Is Laundering ground truth
   - parses HI-Small_Patterns.txt into structured typology examples
   - builds a BOUNDED suspicious-edge graph (see below)
                        v
data/processed/financial-crime/
   account_features.csv    (515,080 rows - full coverage, not a sample)
   suspicious_edges.csv    (20,000 rows, capped - see below)
   laundering_patterns.json
   eval_stats.json
                        v
                 this service (loads all four at startup)
```

Regenerate with:
```bash
python scripts/data_generation/financial_crime/build_transaction_graph.py
```
Takes ~1-2 minutes; the transaction file is 475MB.

## The 5 rules (transparent, not a black box)

| Rule | Trigger |
|---|---|
| `flag_high_fan_out` | distinct outgoing counterparties >= 99th-percentile account (10 in current data) |
| `flag_high_fan_in` | distinct incoming counterparties >= 99th-percentile account (8) |
| `flag_rapid_passthrough` | >=3 in and >=3 out transactions, and total-out/total-in between 0.85-1.15 (funds pass through without accumulating) |
| `flag_cross_currency` | account touches 2+ distinct currencies (layering signal) |
| `flag_high_value_txn` | largest single transaction >= 98th-percentile transaction value (~$34.6M in current data) |

`risk_score` = count of triggered rules (0-5). `risk_tier`: HIGH (>=3),
MEDIUM (==2), LOW (<=1). Every threshold used is in `/api/financial/stats`
and `eval_stats.json` — nothing is a hidden magic number.

## Evaluation — read this before calling anything here "detection"

Against the real ground-truth labels, on the current build:

| Flagging level | Flagged accounts | Precision | Recall | F1 |
|---|---|---|---|---|
| HIGH only | 660 | 14.9% | 1.5% | 2.8% |
| MEDIUM + HIGH | 5,280 | 12.9% | 10.7% | 11.7% |

This is **intentionally reported, not hidden**: five simple structural
rules catch only 10-11% of labeled laundering activity, with ~85-87% of
flags being false positives. That's a genuine, honest finding, not a bug —
two things worth saying out loud in a demo:

1. It's directionally consistent with real-world AML systems, which are
   notorious for high false-positive rates (often cited well above 90%) —
   this rule engine is in a realistic range, not an outlier.
2. It's the strongest argument in this entire platform for why pillar 5
   (a trained risk model, not rule thresholds) matters. This service's
   account-feature table (`account_features.csv`) — with real ground-truth
   labels attached — is a ready-made supervised training set for exactly
   that model.

Don't present the rule engine alone as "AI-powered fraud detection" — present
it as the transparent, explainable baseline layer that a trained model
should be measured against.

## Suspicious-edges graph is capped, on purpose

The full transaction graph has on the order of millions of unique
(sender, receiver) pairs — too large to serve from an in-memory demo
service, and mostly irrelevant to a graph explorer anyway. `suspicious_edges.csv`
keeps only edges where at least one endpoint is HIGH-risk or the edge
carries a ground-truth-laundering-labeled transaction, capped at 20,000
rows. `/api/financial/path` can only route between accounts inside that
subgraph — a path query between two ordinary LOW-risk accounts with no
laundering history will correctly report `found: false` even if a path
exists in the full (unloaded) transaction graph. This is a demo-scoping
decision, not a bug — see `network-analysis`'s README for the same
in-memory-graph caveat pattern.

## Known limitations

- Single HI-Small variant only (5.08M of the full dataset's larger
  HI/LI-Medium/Large variants, up to 17GB) — see `data/raw/MANIFEST.md`.
- Account-level, not sub-account/transaction-level — a flagged account
  doesn't tell you *which* transactions on it look worst without a
  follow-up query against the raw file (not loaded by this service).
- 16 of 515,096 account numbers in `HI-Small_accounts.csv` collide across
  two different banks; the first occurrence wins. Negligible (<0.01%),
  documented in the prep script rather than silently resolved.
- Real-world PII (SWIFT codes, real bank names) does not appear anywhere —
  bank/entity names in this dataset are IBM's own synthetic benchmark
  labels ("Sole Proprietorship #41", "Partnership #35397"), not real
  institutions.

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/financial/stats` | Dataset totals, risk-tier counts, thresholds used. |
| `GET /api/financial/account/{account_id}` | Full risk profile for one account. |
| `GET /api/financial/suspicious-accounts?risk_tier=&limit=` | Accounts at a given risk tier, sorted by risk_score. |
| `GET /api/financial/patterns?typology=&limit=` | Labeled laundering typology examples (370 total, 8 typologies). |
| `GET /api/financial/path?source=&target=` | Shortest path between two accounts in the bounded suspicious-edge graph. |
| `GET /api/financial/evaluate` | Rule-engine precision/recall/F1 against real ground truth. |

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8013
```

## Tests

```bash
python -m pytest tests/ -v
```
