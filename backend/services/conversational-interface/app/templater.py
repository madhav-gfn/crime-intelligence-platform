"""
Turns a downstream service's structured JSON into one plain-English
sentence. The chat response always includes the raw `data` alongside the
sentence (see schemas.ChatResponse) - the sentence is a convenience for
display, never the only copy of the answer, in keeping with the rest of
this platform's stance that a summary should never hide the numbers behind
it.
"""


def person_dossier(d: dict) -> str:
    risk = d.get("offender_risk")
    if risk:
        risk_str = (
            f"{risk['risk_tier']} risk tier "
            f"({risk['predicted_reoffend_probability_365d']:.0%} predicted probability of reoffending within 365 days)"
        )
    else:
        risk_str = "no offender-risk profile on file"
    name = d.get("full_name") or d["person_id"]
    return (
        f"{name} ({d['person_id']}), age {d.get('age', 'unknown')}, "
        f"{d.get('address_district', 'unknown district')}, {d.get('address_state', 'unknown state')}. "
        f"{risk_str}. Linked to {len(d.get('cases', []))} case(s) and "
        f"{d.get('network_degree', 0)} known associate(s)."
    )


def person_risk(d: dict) -> str:
    name = d.get("full_name") or d["person_id"]
    return (
        f"{name} ({d['person_id']}) is {d['risk_tier']} risk: "
        f"{d['predicted_reoffend_probability_365d']:.0%} predicted probability of reoffending within 365 days, "
        f"based on {d['prior_case_count']} prior case(s) across {d['distinct_crime_types_count']} crime type(s)."
    )


def person_explain(d: dict) -> str:
    name = d.get("full_name") or d["person_id"]
    top = d.get("top_drivers", [])
    driver_str = "; ".join(
        f"{c['feature']} ({'+' if c['shap_value'] >= 0 else ''}{c['shap_value']:.3f})" for c in top[:3]
    )
    return (
        f"{name} ({d['person_id']}) is {d['risk_tier']} risk "
        f"({d['predicted_reoffend_probability_365d']:.0%}). Top drivers: {driver_str or 'none'}."
    )


def person_network(d: dict) -> str:
    center = d["center"]
    name = center.get("full_name") or center["person_id"]
    others = [n for n in d.get("nodes", []) if n["person_id"] != center["person_id"]]
    return (
        f"{name} ({center['person_id']})'s network out to depth {d['depth']}: "
        f"{len(others)} associate(s), {len(d.get('edges', []))} shared-case link(s)."
    )


def district_briefing(d: dict) -> str:
    hotspot_str = "a known hotspot" if d.get("is_hotspot") else "not a hotspot"
    soc = d.get("socioeconomic", {})
    soc_str = (
        f", literacy rate {soc['literacy_rate']:.1%}, urbanization {soc['urbanization_rate']:.1%}"
        if soc.get("available") else ""
    )
    return (
        f"{d['district']}, {d['state']}: {d['total_cases']} total case(s), "
        f"{d['unresolved_cases']} unresolved, {hotspot_str} "
        f"(case-volume percentile {d['case_volume_percentile_rank']:.0%}){soc_str}."
    )


def district_forecast(d: dict) -> str:
    total = next((s for s in d.get("series", []) if s["series"] == "TOTAL"), None)
    if total is None:
        return f"No TOTAL-series forecast available for {d['district']}, {d['state']}."
    last_val, forecast_val = total["last_observed_value"], total["forecast_2013"]
    pct = (forecast_val - last_val) / last_val * 100 if last_val else None
    trend = "up" if pct and pct > 0 else "down" if pct and pct < 0 else "flat"
    pct_str = f"{abs(pct):.1f}% {trend}" if pct is not None else "no comparable trend"
    return (
        f"{d['district']}, {d['state']}: forecast total crime for {d['district']} is "
        f"{forecast_val:.0f} (from {last_val:.0f} in {total['last_observed_year']}) - {pct_str}, "
        f"selected model: {total['selected_model']}."
    )


def hotspots(d: dict) -> str:
    clusters = d.get("clusters", [])
    if not clusters:
        return f"No hotspot clusters found with the current filters (eps={d['eps_km']}km, min_points={d['min_points']})."
    top = sorted(clusters, key=lambda c: c["point_count"], reverse=True)[:3]
    top_str = "; ".join(f"{c['top_district']} ({c['point_count']} incidents)" for c in top)
    return f"{len(clusters)} hotspot cluster(s) found. Largest: {top_str}."


def suspicious_accounts(d: dict) -> str:
    accounts = d.get("accounts", [])
    if not accounts:
        return f"No {d['risk_tier']}-risk suspicious accounts found."
    ids = ", ".join(a["account_id"] for a in accounts[:5])
    return f"{d['count']} {d['risk_tier']}-risk suspicious account(s) found. Top: {ids}."


def case_priority(d: dict) -> str:
    cases = d.get("cases", [])
    if not cases:
        tier_str = f" at tier {d['priority_tier']}" if d.get("priority_tier") else ""
        return f"No unresolved cases found{tier_str}."
    top = cases[0]
    return (
        f"{d['count']} unresolved case(s)"
        + (f" at tier {d['priority_tier']}" if d.get("priority_tier") else "")
        + f". Highest priority: FIR {top['fir_id']} in {top['district']} "
        f"(score {top['priority_score']}, {top['priority_tier']})."
    )


def repeat_offenders(d: list) -> str:
    if not d:
        return "No repeat offenders found with the current filters."
    top = d[0]
    return (
        f"{len(d)} repeat offender(s) found. Highest case count: "
        f"{top['full_name']} ({top['person_id']}) with {top['prior_case_count']} prior case(s), "
        f"{top['risk_tier']} risk."
    )


TEMPLATES = {
    "person_dossier": person_dossier,
    "person_risk": person_risk,
    "person_explain": person_explain,
    "person_network": person_network,
    "district_briefing": district_briefing,
    "district_forecast": district_forecast,
    "hotspots": hotspots,
    "suspicious_accounts": suspicious_accounts,
    "case_priority": case_priority,
    "repeat_offenders": repeat_offenders,
}


def render(intent: str, data) -> str:
    template = TEMPLATES.get(intent)
    if template is None:
        return "Here's what I found."
    try:
        return template(data)
    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return "Found a result, but couldn't summarize it cleanly - see the raw data below."
