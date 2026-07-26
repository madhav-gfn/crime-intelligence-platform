# conversational-interface

Conversational interface (pillar 1) - the platform's natural-language front
door. A single `POST /api/chat/message` endpoint that accepts a short
English query and routes it to whichever of the other seven analytics
services actually holds the answer.

## Why this isn't the research doc's dialogue engine

`docs/architecture/Conversational Crime Analytics AI Research.md` describes
an LLM/LangGraph-based dialogue system with Whisper ASR and Kannada speech
synthesis. None of that is buildable in this environment - there is no LLM
API key available, and ASR/TTS require audio infrastructure and vendor
SDKs that are out of scope for a backend demo. Rather than stub that out
with a fake "AI" that doesn't actually work, this service implements the
one part of that vision that doesn't require an LLM at all: turning a
fairly formulaic investigator query into the right downstream API call,
deterministically.

| Research-doc component | This build |
|---|---|
| LLM-based NLU / intent understanding | Ordered regex/keyword intent classification (`app/nlu.py`) - a fixed set of recognized question shapes, not open-ended free text. Honestly reported as such via `/api/chat/capabilities`. |
| LangGraph dialogue-state graph | A plain per-session context dict (`app/session_store.py`) tracking the last-mentioned person/district, resolving follow-ups like "why is he high risk?" |
| Whisper ASR / Kannada TTS/G2P | Not implemented - text-only, English-only. No audio pipeline exists in this repo. |
| Session PDF export | Not implemented - `GET /api/chat/session/{id}/history` returns the raw turn log instead. |

If an LLM API key becomes available, the natural place to plug it in is
`app/nlu.py`'s `parse()` function (replace regex classification with a
model call) - the orchestration/routing layer below it doesn't need to
change.

## Why this service calls other services over HTTP, unlike the rest of the platform

Every other cross-service consumer in this platform (`investigator-decision-support`,
`explainable-ai`) reads precomputed files directly from
`data/processed/*` instead of making live HTTP calls - a deliberate choice
documented in both their READMEs, trading live-service availability for
demo reliability and graceful degradation.

This service does the opposite, on purpose: a chat message can address any
of seven different analytics domains unpredictably (a person's risk score
one turn, a district's crime forecast the next). Reading each of those
domains' files directly here would mean re-implementing seven services'
worth of query/join logic a second time and keeping every copy in sync by
hand - a much worse tradeoff than the one file-reading was chosen to avoid
elsewhere. Delegating over HTTP keeps one source of truth per domain, at
the honest cost that a chat query fails informatively (not silently) if
the relevant downstream service isn't running (see `app/orchestrator.py`'s
handling of connection errors).

## Authorization is a pass-through, not a re-implementation

`/api/chat/message` itself only requires `ANALYST` - the floor everywhere
else in this platform. It never makes its own decision about who can see
what: the caller's own bearer token is forwarded unchanged to whichever
downstream service actually answers the query, and that service's real
RBAC check is what decides. If an `ANALYST` asks "who is ACC-002543" (a
person-dossier question, which `investigator-decision-support` gates at
`INVESTIGATOR`), the resulting 403 is surfaced honestly as a chat reply
(`downstream_status: 403`) - not silently retried, escalated, or
swallowed.

## Supported intents

| Intent | Example phrasing | Downstream service |
|---|---|---|
| `person_dossier` | "who is ACC-002543" | `investigator-decision-support` |
| `person_risk` | "what is the risk score for ACC-002543" | `offender-profiling` |
| `person_explain` | "why is ACC-002543 high risk" | `explainable-ai` |
| `person_network` | "who is ACC-002543 connected to" | `network-analysis` |
| `district_briefing` | "brief me on Bidar" | `investigator-decision-support` |
| `district_forecast` | "forecast for Bidar" | `crime-forecasting` |
| `hotspots` | "show me crime hotspots" | `pattern-analytics` |
| `suspicious_accounts` | "show suspicious accounts" | `financial-crime-analysis` |
| `case_priority` | "top priority cases" | `investigator-decision-support` |
| `repeat_offenders` | "repeat offenders" | `network-analysis` |
| `help` | "help" / "what can you do" | none - lists the table above |

Person references accept a real `person_id` (`ACC-002543`, `VIC-000001`,
`CMP-000001`) or a pronoun/back-reference ("he", "him", "this person") that
resolves to whoever was last discussed in the same `session_id`. District
references are matched against the ~660 real district names in the seed
data (`app/nlu.py`'s `DistrictIndex`, case-insensitive substring match).
Missing a required entity gets a clarifying reply, not a guess or a 500.

## Endpoints (all require `Authorization: Bearer <token>` - see auth-service)

| Endpoint | Min. role | Description |
|---|---|---|
| `POST /api/chat/message` | `ANALYST` | `{message, session_id?}` -> intent, extracted entities, a plain-English reply, and the raw downstream JSON. |
| `GET /api/chat/capabilities` | `ANALYST` | The supported-intents table above, as structured data. |
| `GET /api/chat/session/{session_id}/history` | `ANALYST` | Full turn history for a session, including resolved `last_person_id`/`last_district`. |

`/api/chat/message` is this service's one `POST` endpoint - the second
exception (after `auth-service`'s login) to the platform's GET-only
convention, here for a practical reason rather than a security one: a
natural-language message is free text that doesn't belong in a query
string.

Session state is **in-memory, resets on service restart** - the same
documented limitation as `auth-service`'s audit log. A real deployment
would back this with a shared store (Redis, a session table) so it
survives restarts and works across multiple app instances.

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8022
```

Talks to the other seven services over HTTP - see `.env.example` for their
default localhost ports. Start whichever ones you want to query before
sending chat messages; an unreachable service produces an honest "isn't
reachable right now" reply, not a crash.

## Tests

```bash
python -m pytest tests/ -v
```

Downstream calls are exercised against a real `httpx.MockTransport` (see
`tests/test_chat_api.py`), not against live services - covering intent
routing, entity extraction, pronoun/context resolution across turns, and
honest propagation of 403s and connection failures. The service was also
smoke-tested live against a running `investigator-decision-support`
instance with a real signed JWT.

## Deployment

See [docs/deployment/DEPLOY.md](../../../docs/deployment/DEPLOY.md) for the
Zoho Catalyst AppSail deploy guide (backend-only, no frontend yet). Deploy
this service **last** - its `app-config.json` needs the other 7 services'
real deployed URLs filled in before it can route anything.
