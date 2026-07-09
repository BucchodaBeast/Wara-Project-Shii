"""
matching_engine.py

The core engineering feature of the platform. Given a Request (a need) and a
pool of candidate Offers (or vice versa), this module scores every possible
pairing with a weighted formula instead of a plain category filter:

    score = (URGENCY_WEIGHT   * urgency_score)
          + (DISTANCE_WEIGHT  * proximity_score)
          + (TYPE_WEIGHT      * resource_type_score)

Every function here is pure (no DB or network calls) so it can be unit
tested in isolation and reused from both the citizen-facing submit flow
and the coordinator dashboard's "recompute" action.
"""

import math

URGENCY_WEIGHT = 0.40
DISTANCE_WEIGHT = 0.35
TYPE_WEIGHT = 0.25

URGENCY_SCORES = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}

# Loose synonym map so "medical" needs can partially match "first_aid" offers,
# etc. Exact matches always score highest.
RELATED_CATEGORIES = {
    "medical": {"first_aid", "medicine", "health"},
    "water": {"drinking_water", "sanitation"},
    "food": {"groceries", "meal", "supplies"},
    "shelter": {"housing", "blankets", "tent"},
    "transport": {"truck", "vehicle", "fuel"},
}

MAX_RELEVANT_DISTANCE_KM = 50.0  # beyond this, proximity score bottoms out at 0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    if None in (lat1, lon1, lat2, lon2):
        return MAX_RELEVANT_DISTANCE_KM  # unknown location = treat as far away
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def proximity_score(distance_km: float) -> float:
    """Linear decay: 0km -> 1.0, MAX_RELEVANT_DISTANCE_KM+ -> 0.0"""
    if distance_km >= MAX_RELEVANT_DISTANCE_KM:
        return 0.0
    return max(0.0, 1.0 - (distance_km / MAX_RELEVANT_DISTANCE_KM))


def resource_type_score(need_category: str, offer_type: str) -> float:
    need_category = (need_category or "").strip().lower()
    offer_type = (offer_type or "").strip().lower()

    if need_category == offer_type:
        return 1.0
    if offer_type in RELATED_CATEGORIES.get(need_category, set()):
        return 0.5
    return 0.1  # unrelated but not excluded outright — coordinator can still see it


def score_pair(request_row: dict, offer_row: dict) -> dict:
    """
    Scores one (request, offer) pairing.
    Both rows are expected to have: category/resource_type, urgency (request
    only), latitude, longitude.
    Returns a dict with score (0-100), distance_km, and a breakdown for
    transparency on the coordinator dashboard.
    """
    urgency = URGENCY_SCORES.get((request_row.get("urgency") or "").lower(), 0.5)
    distance_km = haversine_km(
        request_row.get("latitude"), request_row.get("longitude"),
        offer_row.get("latitude"), offer_row.get("longitude"),
    )
    proximity = proximity_score(distance_km)
    type_match = resource_type_score(request_row.get("category"), offer_row.get("resource_type"))

    raw = (URGENCY_WEIGHT * urgency) + (DISTANCE_WEIGHT * proximity) + (TYPE_WEIGHT * type_match)

    return {
        "score": round(raw * 100, 1),
        "distance_km": round(distance_km, 2),
        "breakdown": {
            "urgency": round(urgency * 100, 1),
            "proximity": round(proximity * 100, 1),
            "type_match": round(type_match * 100, 1),
        },
    }


def compute_matches(request_row: dict, candidate_offers: list) -> list:
    """
    Scores a request against every candidate offer and returns the results
    sorted by score, descending. Only offers with status == 'available' and
    the same broad category family should be passed in by the caller for
    efficiency, but this function itself does not filter — it scores whatever
    it's given.
    """
    results = []
    for offer in candidate_offers:
        result = score_pair(request_row, offer)
        results.append({
            "offer_id": offer["id"],
            "request_id": request_row["id"],
            **result,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results
