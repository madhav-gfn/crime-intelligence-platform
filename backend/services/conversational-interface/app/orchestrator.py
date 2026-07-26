"""
Resolves a parsed query (see app/nlu.py) plus session context into exactly
one downstream API call, and turns the result (or the failure) into a
ChatResponse. This is the one place that knows which service owns which
answer.

Every downstream call forwards the caller's own Authorization header
unchanged - this service never elevates privilege or makes its own
decision about who can see what. If an ANALYST asks "who is ACC-002543"
(a person-dossier question, which investigator-decision-support gates at
INVESTIGATOR), the downstream 403 is surfaced honestly as a chat reply,
not silently retried with different credentials or swallowed.
"""
from urllib.parse import quote

import httpx

from app.nlu import ParsedQuery
from app.session_store import Session

CLARIFY_PERSON = (
    "Which person? Include a person ID like ACC-002543, VIC-000001, or CMP-000001, "
    "or ask a follow-up about someone already mentioned in this conversation."
)
CLARIFY_DISTRICT = "Which district? I couldn't recognize a district name in that message."

CAPABILITIES = {
    "person_dossier": "who is <person_id> / tell me about <person_id> - full cross-service profile",
    "person_risk": "what is the risk score for <person_id> - offender-profiling's recidivism prediction",
    "person_explain": "why is <person_id> high risk / explain <person_id> - SHAP-based explanation",
    "person_network": "who is <person_id> connected to - co-accused network",
    "district_briefing": "brief me on <district> - case volume, hotspot status, socioeconomic context",
    "district_forecast": "forecast for <district> - projected crime trend",
    "hotspots": "show me crime hotspots - DBSCAN spatial clusters",
    "suspicious_accounts": "show suspicious accounts - financial crime flags",
    "case_priority": "top priority cases - unresolved cases ranked by urgency",
    "repeat_offenders": "repeat offenders - persons with multiple prior cases",
}


class Orchestrator:
    def __init__(self, client: httpx.AsyncClient, settings):
        self.client = client
        self.settings = settings

    def _url(self, base: str, path: str) -> str:
        return f"{base.rstrip('/')}{path}"

    async def _get(self, base: str, path: str, token: str, params: dict | None = None):
        url = self._url(base, path)
        try:
            resp = await self.client.get(
                url, params=params, headers={"Authorization": token},
                timeout=self.settings.downstream_timeout_seconds,
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return None, None
        return resp.status_code, resp

    async def answer(self, parsed: ParsedQuery, session: Session, token: str) -> dict:
        if parsed.intent == "help":
            return {
                "intent": "help", "reply": "I can answer these kinds of questions:",
                "downstream_service": None, "downstream_status": None, "data": CAPABILITIES,
            }

        if parsed.intent == "unknown":
            return {
                "intent": "unknown",
                "reply": "I didn't recognize that as one of the questions I can answer. Try 'help' to see examples.",
                "downstream_service": None, "downstream_status": None, "data": None,
            }

        person_id = parsed.person_id or (session.last_person_id if parsed.person_from_context else None)
        district = parsed.district or (session.last_district if parsed.district_from_context else None)

        handler = self._HANDLERS.get(parsed.intent)
        if handler is None:
            return {
                "intent": parsed.intent, "reply": "I recognized the question type but don't have a handler for it yet.",
                "downstream_service": None, "downstream_status": None, "data": None,
            }

        needs_person = parsed.intent in {"person_dossier", "person_risk", "person_explain", "person_network"}
        needs_district = parsed.intent in {"district_briefing", "district_forecast"}
        if needs_person and not person_id:
            return {
                "intent": parsed.intent, "reply": CLARIFY_PERSON,
                "downstream_service": None, "downstream_status": None, "data": None,
            }
        if needs_district and not district:
            return {
                "intent": parsed.intent, "reply": CLARIFY_DISTRICT,
                "downstream_service": None, "downstream_status": None, "data": None,
            }

        service_name, status, resp = await handler(self, parsed, person_id, district, token)

        if status is None:
            return {
                "intent": parsed.intent, "reply": f"The {service_name} service isn't reachable right now.",
                "downstream_service": service_name, "downstream_status": None, "data": None,
            }
        if status == 404:
            detail = resp.json().get("detail", "not found") if resp.headers.get("content-type", "").startswith("application/json") else "not found"
            return {
                "intent": parsed.intent, "reply": detail,
                "downstream_service": service_name, "downstream_status": status, "data": None,
            }
        if status in (401, 403):
            detail = resp.json().get("detail", "access denied")
            return {
                "intent": parsed.intent, "reply": f"Access denied: {detail}",
                "downstream_service": service_name, "downstream_status": status, "data": None,
            }
        if status >= 400:
            return {
                "intent": parsed.intent, "reply": f"The {service_name} service returned an error (HTTP {status}).",
                "downstream_service": service_name, "downstream_status": status, "data": None,
            }

        data = resp.json()
        if person_id:
            session.last_person_id = person_id
        if district:
            session.last_district = district
        from app.templater import render
        return {
            "intent": parsed.intent, "reply": render(parsed.intent, data),
            "downstream_service": service_name, "downstream_status": status, "data": data,
        }

    # ---- per-intent downstream calls ---------------------------------------

    async def _h_person_dossier(self, parsed, person_id, district, token):
        s = "investigator-decision-support"
        status, resp = await self._get(
            self.settings.investigator_decision_support_url,
            f"/api/decision-support/person-dossier/{quote(person_id)}", token,
        )
        return s, status, resp

    async def _h_person_risk(self, parsed, person_id, district, token):
        s = "offender-profiling"
        status, resp = await self._get(
            self.settings.offender_profiling_url, f"/api/offender-profiling/person/{quote(person_id)}", token,
        )
        return s, status, resp

    async def _h_person_explain(self, parsed, person_id, district, token):
        s = "explainable-ai"
        status, resp = await self._get(
            self.settings.explainable_ai_url, f"/api/explainability/person/{quote(person_id)}", token,
        )
        return s, status, resp

    async def _h_person_network(self, parsed, person_id, district, token):
        s = "network-analysis"
        status, resp = await self._get(
            self.settings.network_analysis_url, f"/api/network/person/{quote(person_id)}/ego", token,
        )
        return s, status, resp

    async def _h_district_briefing(self, parsed, person_id, district, token):
        s = "investigator-decision-support"
        status, resp = await self._get(
            self.settings.investigator_decision_support_url,
            f"/api/decision-support/district-briefing/{quote(district)}", token,
        )
        return s, status, resp

    async def _h_district_forecast(self, parsed, person_id, district, token):
        s = "crime-forecasting"
        status, resp = await self._get(
            self.settings.crime_forecasting_url, f"/api/forecasting/district/{quote(district)}", token,
        )
        return s, status, resp

    async def _h_hotspots(self, parsed, person_id, district, token):
        s = "pattern-analytics"
        params = {"district": district} if district else None
        status, resp = await self._get(self.settings.pattern_analytics_url, "/api/patterns/hotspots", token, params)
        return s, status, resp

    async def _h_suspicious_accounts(self, parsed, person_id, district, token):
        s = "financial-crime-analysis"
        params = {"risk_tier": parsed.risk_tier} if parsed.risk_tier else None
        status, resp = await self._get(
            self.settings.financial_crime_analysis_url, "/api/financial/suspicious-accounts", token, params,
        )
        return s, status, resp

    async def _h_case_priority(self, parsed, person_id, district, token):
        s = "investigator-decision-support"
        params = {"priority_tier": parsed.risk_tier} if parsed.risk_tier else None
        status, resp = await self._get(
            self.settings.investigator_decision_support_url, "/api/decision-support/case-priority", token, params,
        )
        return s, status, resp

    async def _h_repeat_offenders(self, parsed, person_id, district, token):
        s = "network-analysis"
        status, resp = await self._get(self.settings.network_analysis_url, "/api/network/repeat-offenders", token)
        return s, status, resp

    _HANDLERS = {
        "person_dossier": _h_person_dossier,
        "person_risk": _h_person_risk,
        "person_explain": _h_person_explain,
        "person_network": _h_person_network,
        "district_briefing": _h_district_briefing,
        "district_forecast": _h_district_forecast,
        "hotspots": _h_hotspots,
        "suspicious_accounts": _h_suspicious_accounts,
        "case_priority": _h_case_priority,
        "repeat_offenders": _h_repeat_offenders,
    }
