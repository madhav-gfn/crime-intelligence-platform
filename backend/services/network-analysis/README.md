# Network Analysis Service

FastAPI service for pillar 2 (Criminal Network & Relationship Analysis):
co-accused graphs, organized-group detection, key-actor ranking, association
paths between suspects, and repeat-offender lookups.

Runs on the calibrated synthetic seed dataset in `data/seed/` (see
`data/schemas/synthetic_fir_schema.md` for what's real vs. synthetic). Swap
`GraphStore` in `app/graph_store.py` for a real graph database query layer
when this moves past prototype scale - the router/schema layer doesn't need
to change.

## Setup

```bash
cd backend/services/network-analysis
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
```

## Run

```bash
./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8010
```

Docs at `http://127.0.0.1:8010/docs`.

## Test

```bash
./.venv/Scripts/python -m pytest tests/ -v
```

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/network/stats` | Graph-wide summary (node/edge counts, community count, avg degree) |
| `GET /api/network/graph` | Nodes+edges for visualization, filterable by district / min shared cases / node cap |
| `GET /api/network/person/{id}` | Single person's profile + network degree |
| `GET /api/network/person/{id}/ego` | A person's local network out to N hops - "who is this suspect connected to" |
| `GET /api/network/communities` | Louvain-detected clusters - candidate organized-crime groups, each with a core member and shared crime types |
| `GET /api/network/hubs` | Top actors by degree/betweenness centrality - "who are the key figures" |
| `GET /api/network/path` | Shortest association path between two people, with the shared-FIR evidence for every hop (explainability) |
| `GET /api/network/repeat-offenders` | Offenders sorted by prior case count |

Every edge in every response carries `fir_ids` - the specific cases the
connection is based on - so any claim the API makes ("these two are linked")
traces back to source records, per the platform's explainability requirement.

## Known limitation
In-memory graph, loaded once at startup from CSV. Fine for the ~11k-person
demo dataset; would need to move to a real graph database and incremental
loading before handling a live, growing case database.
