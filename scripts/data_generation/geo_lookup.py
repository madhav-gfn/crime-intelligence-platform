"""
District -> (lat, lon) resolution for synthetic FIR geocoding.

Two tiers, both explicitly labeled so downstream consumers know which
districts have real coordinates vs. an approximated fallback:

1. CITY_CENTROIDS: curated real coordinates for ~55 major
   districts/cities, covering essentially all of the highest-crime-volume
   districts from the NCRB calibration (see calibrate_ncrb.py output).
   These get exact, precise=True coordinates.

2. STATE_CAPITAL_CENTROIDS: fallback for the ~750 remaining, lower-volume
   districts not individually curated. Each such district is deterministically
   jittered around its state capital (same district name -> same offset every
   run) so records scatter realistically on a map instead of stacking on one
   point, but precise=False flags that this is NOT a real geocode.
"""
import hashlib
import re

CITY_CENTROIDS = {
    "MUMBAI": (19.0760, 72.8777),
    "PUNE": (18.5204, 73.8567),
    "THANE": (19.2183, 72.9781),
    "NAGPUR": (21.1458, 79.0882),
    "NASHIK": (19.9975, 73.7898),
    "BANGALORE": (12.9716, 77.5946),
    "BENGALURU": (12.9716, 77.5946),
    "MYSORE": (12.2958, 76.6394),
    "KOLKATA": (22.5726, 88.3639),
    "HOWRAH": (22.5958, 88.2636),
    "24 PARGANAS NORTH": (22.6167, 88.4000),
    "24 PARGANAS SOUTH": (22.1667, 88.4000),
    "MURSHIDABAD": (24.1833, 88.2667),
    "NADIA": (23.4058, 88.5417),
    "AHMEDABAD": (23.0225, 72.5714),
    "SURAT": (21.1702, 72.8311),
    "VADODARA": (22.3072, 73.1812),
    "RAJKOT": (22.3039, 70.8022),
    "INDORE": (22.7196, 75.8577),
    "BHOPAL": (23.2599, 77.4126),
    "JABALPUR": (23.1815, 79.9864),
    "GWALIOR": (26.2183, 78.1828),
    "SAGAR": (23.8388, 78.7378),
    "CHENNAI": (13.0827, 80.2707),
    "COIMBATORE": (11.0168, 76.9558),
    "CUDDALORE": (11.7480, 79.7714),
    "VILLUPURAM": (11.9401, 79.4861),
    "THIRUNELVELI": (8.7139, 77.7567),
    "MADURAI": (9.9252, 78.1198),
    "CYBERABAD": (17.4435, 78.3772),
    "HYDERABAD": (17.3850, 78.4867),
    "KARIMNAGAR": (18.4386, 79.1288),
    "NALGONDA": (17.0575, 79.2690),
    "ERNAKULAM": (9.9816, 76.2999),
    "MALAPPURAM": (11.0510, 76.0711),
    "THRISSUR": (10.5276, 76.2144),
    "KOTTAYAM": (9.5916, 76.5222),
    "TRIVANDRUM": (8.5241, 76.9366),
    "PALAKKAD": (10.7867, 76.6548),
    "ALAPUZHA": (9.4981, 76.3388),
    "PATNA": (25.5941, 85.1376),
    "LUCKNOW": (26.8467, 80.9462),
    "AGRA": (27.1767, 78.0081),
    "KANPUR": (26.4499, 80.3319),
    "VARANASI": (25.3176, 82.9739),
    "ALWAR": (27.5530, 76.6346),
    "BHARATPUR": (27.2152, 77.4977),
    "JAIPUR": (26.9124, 75.7873),
    "GUWAHATI": (26.1445, 91.7362),
    "DELHI": (28.6139, 77.2090),
    "KANNUR": (11.8745, 75.3704),
    "RAIPUR": (21.2514, 81.6296),
    "UJJAIN": (23.1765, 75.7885),
    "KANCHIPURAM": (12.8342, 79.7036),
    "UDAIPUR": (24.5854, 73.7125),
    "MEERUT": (28.9845, 77.7064),
    "WEST GODAVARI": (16.9107, 81.3399),
    "JALPAIGURI": (26.5167, 88.7333),
    "MOTIHARI": (26.6485, 84.9147),
}

STATE_CAPITAL_CENTROIDS = {
    "ANDHRA PRADESH": (17.3850, 78.4867),
    "ARUNACHAL PRADESH": (27.0844, 93.6053),
    "ASSAM": (26.1445, 91.7362),
    "BIHAR": (25.5941, 85.1376),
    "CHHATTISGARH": (21.2514, 81.6296),
    "GOA": (15.4909, 73.8278),
    "GUJARAT": (23.0225, 72.5714),
    "HARYANA": (30.7333, 76.7794),
    "HIMACHAL PRADESH": (31.1048, 77.1734),
    "JAMMU & KASHMIR": (34.0837, 74.7973),
    "JHARKHAND": (23.3441, 85.3096),
    "KARNATAKA": (12.9716, 77.5946),
    "KERALA": (8.5241, 76.9366),
    "MADHYA PRADESH": (23.2599, 77.4126),
    "MAHARASHTRA": (19.0760, 72.8777),
    "MANIPUR": (24.8170, 93.9368),
    "MEGHALAYA": (25.5788, 91.8933),
    "MIZORAM": (23.7271, 92.7176),
    "NAGALAND": (25.6751, 94.1086),
    "ODISHA": (20.2961, 85.8245),
    "PUNJAB": (30.7333, 76.7794),
    "RAJASTHAN": (26.9124, 75.7873),
    "SIKKIM": (27.3389, 88.6065),
    "TAMIL NADU": (13.0827, 80.2707),
    "TRIPURA": (23.8315, 91.2868),
    "UTTAR PRADESH": (26.8467, 80.9462),
    "UTTARAKHAND": (30.3165, 78.0322),
    "WEST BENGAL": (22.5726, 88.3639),
    "DELHI": (28.6139, 77.2090),
    "DELHI UT": (28.6139, 77.2090),
    "PUDUCHERRY": (11.9416, 79.8083),
    "CHANDIGARH": (30.7333, 76.7794),
    "ANDAMAN & NICOBAR ISLANDS": (11.6234, 92.7265),
    "DADRA & NAGAR HAVELI": (20.1809, 73.0169),
    "DAMAN & DIU": (20.1809, 73.0169),
    "LAKSHADWEEP": (10.5593, 72.6358),
}

# Only administrative/jurisdiction suffixes are stripped here - NOT directional
# words (EAST/WEST/NORTH/SOUTH), since those are load-bearing in real district
# names like "24 PARGANAS SOUTH" or "WEST GODAVARI".
_SUFFIX_PATTERN = re.compile(r"\b(COMMR\.?|RURAL|URBAN|CITY|TOTAL|DT\.?|GRP\.?)\b")


def _normalize(district: str) -> str:
    name = _SUFFIX_PATTERN.sub("", district.upper()).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _lookup_city(district: str) -> tuple[float, float] | None:
    exact = district.upper().strip()
    if exact in CITY_CENTROIDS:
        return CITY_CENTROIDS[exact]

    stripped = _normalize(district)
    if stripped in CITY_CENTROIDS:
        return CITY_CENTROIDS[stripped]

    # last resort: does the district name start with a known city (handles
    # "MUMBAI COMMR." style suffixes the regex above didn't fully clear)
    first_word = stripped.split(" ")[0] if stripped else ""
    if first_word in CITY_CENTROIDS:
        return CITY_CENTROIDS[first_word]

    return None


def _jitter(seed_text: str, max_degrees: float = 0.6) -> tuple[float, float]:
    """Deterministic pseudo-random offset so the same district always lands
    at the same fallback point across generator runs."""
    h = hashlib.sha256(seed_text.encode()).hexdigest()
    dx = (int(h[:8], 16) / 0xFFFFFFFF - 0.5) * 2 * max_degrees
    dy = (int(h[8:16], 16) / 0xFFFFFFFF - 0.5) * 2 * max_degrees
    return dx, dy


def get_coordinates(state: str, district: str) -> tuple[float, float, bool]:
    """Returns (lat, lon, precise). precise=True only for curated real centroids."""
    hit = _lookup_city(district)
    if hit is not None:
        return hit[0], hit[1], True

    state_key = state.strip().upper()
    base_lat, base_lon = STATE_CAPITAL_CENTROIDS.get(state_key, (22.9734, 78.6569))  # India centroid fallback
    dx, dy = _jitter(f"{state_key}|{district}")
    return round(base_lat + dx, 5), round(base_lon + dy, 5), False
