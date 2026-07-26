"""
Deterministic, rule-based intent classification and entity extraction.

The platform's research doc (docs/architecture/Conversational Crime
Analytics AI Research.md) describes an LLM/LangGraph-based dialogue engine
with Whisper ASR and Kannada speech synthesis. None of that is buildable
here - there is no LLM API key available in this environment, and ASR/TTS
require audio infrastructure and vendor SDKs out of scope for a backend
demo. What this module implements instead is the part of that vision that
doesn't require an LLM at all: turning a short, fairly formulaic
investigator query ("who is ACC-002543", "forecast for Mysuru", "why is
this person high risk") into a specific downstream API call, via ordered
regex/keyword matching rather than a learned model. It covers the query
shapes this platform's own services actually support - not open-ended
free text - and says so honestly in /api/chat/capabilities rather than
pretending to be a general-purpose assistant.
"""
import re
from dataclasses import dataclass, field

PERSON_ID_RE = re.compile(r"\b(?:VIC|CMP|ACC)-\d{6}\b", re.IGNORECASE)
FIR_ID_RE = re.compile(r"\b\d{15,20}\b")
RISK_TIER_RE = re.compile(r"\b(HIGH|MEDIUM|LOW)\b", re.IGNORECASE)

PERSON_PRONOUN_RE = re.compile(
    r"\b(him|her|them|he|she|they|his|their|this person|that person|the same person)\b", re.IGNORECASE
)
DISTRICT_PRONOUN_RE = re.compile(
    r"\b(there|that district|this district|the same district|that area)\b", re.IGNORECASE
)

# Ordered: first pattern that matches wins. More specific intents (why is
# X risky, who is X connected to) are listed before the generic ones they'd
# otherwise be swallowed by (risk lookup, person dossier).
INTENT_PATTERNS = [
    ("help", re.compile(r"\b(help|what can you do|capabilities|commands|examples?)\b", re.IGNORECASE)),
    ("person_explain", re.compile(r"\b(why|explain)\b", re.IGNORECASE)),
    ("person_network", re.compile(
        r"\b(connect(ed|ions?)?|associat(e|es|ed)|network|linked to|co-accused)\b", re.IGNORECASE
    )),
    ("person_risk", re.compile(r"\b(risk (score|tier|profile)|reoffend|recidivis\w*)\b", re.IGNORECASE)),
    ("person_dossier", re.compile(
        r"\b(who is|tell me about|dossier|profile for|background on|show me person)\b", re.IGNORECASE
    )),
    ("district_forecast", re.compile(r"\b(forecast|predicted crime|crime trend|projection)\b", re.IGNORECASE)),
    ("district_briefing", re.compile(
        r"\b(brief(ing)?|what'?s happening in|situation in|overview of|going on in)\b", re.IGNORECASE
    )),
    ("hotspots", re.compile(r"\bhotspot", re.IGNORECASE)),
    ("suspicious_accounts", re.compile(
        r"\b(suspicious account|financial fraud|money laundering|\baml\b)\b", re.IGNORECASE
    )),
    ("case_priority", re.compile(r"\b(priority case|urgent case|top case|unresolved case)\b", re.IGNORECASE)),
    ("repeat_offenders", re.compile(r"\brepeat offender", re.IGNORECASE)),
]


@dataclass
class ParsedQuery:
    intent: str
    person_id: str | None = None
    fir_id: str | None = None
    district: str | None = None
    risk_tier: str | None = None
    person_from_context: bool = False
    district_from_context: bool = False
    raw_entities: dict = field(default_factory=dict)


class DistrictIndex:
    """Case-insensitive substring lookup against the ~660 real district
    names in the seed data. Longest name first so "24 PARGANAS NORTH"
    doesn't get pre-empted by a shorter unrelated match."""

    def __init__(self, districts: list[str]):
        self._sorted = sorted({d for d in districts if isinstance(d, str) and d.strip()}, key=len, reverse=True)

    def find_in(self, text: str) -> str | None:
        lowered = text.lower()
        for district in self._sorted:
            if district.lower() in lowered:
                return district
        return None


def classify_intent(message: str) -> str:
    for intent, pattern in INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return "unknown"


def parse(message: str, district_index: DistrictIndex) -> ParsedQuery:
    intent = classify_intent(message)

    person_match = PERSON_ID_RE.search(message)
    person_id = person_match.group(0).upper() if person_match else None

    fir_match = FIR_ID_RE.search(message)
    fir_id = fir_match.group(0) if fir_match else None

    risk_match = RISK_TIER_RE.search(message)
    risk_tier = risk_match.group(1).upper() if risk_match else None

    district = district_index.find_in(message)

    person_from_context = person_id is None and bool(PERSON_PRONOUN_RE.search(message))
    district_from_context = district is None and bool(DISTRICT_PRONOUN_RE.search(message))

    return ParsedQuery(
        intent=intent,
        person_id=person_id,
        fir_id=fir_id,
        district=district,
        risk_tier=risk_tier,
        person_from_context=person_from_context,
        district_from_context=district_from_context,
        raw_entities={
            "person_id": person_id, "fir_id": fir_id, "district": district, "risk_tier": risk_tier,
        },
    )
