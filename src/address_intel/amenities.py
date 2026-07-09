"""Nearby amenities via Google Places API (New).

Google returns actual place names and lat/lon coordinates — not a pre-built score.
We compute an amenity score from nearby place counts and proximity.

Cost controls: batched requests (3 calls/address), monthly cap, aggressive caching.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import requests

from ..config import get_google_maps_api_key
from .google_usage import (
    calls_per_amenity_fetch,
    can_fetch_amenities,
    reserve_calls,
)

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

AMENITY_CATEGORIES: list[tuple[str, str]] = [
    ("grocery_store", "Grocery Stores"),
    ("pharmacy", "Pharmacies"),
    ("gym", "Gyms & Fitness"),
    ("convenience_store", "Convenience Stores"),
    ("restaurant", "Restaurants"),
    ("school", "Schools"),
    ("hospital", "Hospitals"),
    ("park", "Parks"),
    ("bank", "Banks"),
    ("shopping_mall", "Shopping"),
]

# 3 API calls per address (was 10) — groups of types in one Nearby Search each
TYPE_BATCHES: list[list[str]] = [
    ["grocery_store", "pharmacy", "convenience_store", "bank"],
    ["gym", "restaurant", "shopping_mall"],
    ["school", "hospital", "park"],
]

TYPE_TO_LABEL = {t: label for t, label in AMENITY_CATEGORIES}


@dataclass
class AmenityPlace:
    name: str
    latitude: float
    longitude: float
    place_type: str
    distance_mi: float
    rating: float | None = None


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def _category_score(count: int, nearest_mi: float | None, radius_miles: float) -> float:
    count_part = min(100.0, count * 20.0)
    if nearest_mi is None:
        dist_part = 0.0
    elif nearest_mi <= 0.25:
        dist_part = 100.0
    else:
        dist_part = max(0.0, 100.0 * (1 - nearest_mi / max(radius_miles, 0.1)))
    return round(0.6 * count_part + 0.4 * dist_part, 1)


def _match_category(types: list[str] | None, primary: str | None) -> str | None:
    """Map a Google place to one of our amenity categories."""
    candidates = []
    if primary:
        candidates.append(primary)
    if types:
        candidates.extend(types)
    for cat_type, _ in AMENITY_CATEGORIES:
        for t in candidates:
            if t == cat_type or t.replace("_", " ") == cat_type.replace("_", " "):
                return cat_type
            if cat_type in t or t in cat_type:
                return cat_type
    return None


def _search_nearby_batch(
    latitude: float,
    longitude: float,
    place_types: list[str],
    radius_meters: float,
    api_key: str,
    max_results: int = 20,
) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,places.location,places.rating,"
            "places.primaryType,places.types"
        ),
    }
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": min(radius_meters, 50000),
            }
        },
        "includedTypes": place_types,
        "maxResultCount": max_results,
    }
    response = requests.post(PLACES_NEARBY_URL, headers=headers, json=body, timeout=30)
    if response.status_code != 200:
        return []
    return response.json().get("places") or []


def fetch_amenities(
    latitude: float,
    longitude: float,
    radius_miles: float = 1.0,
    api_key: str | None = None,
    session_calls_used: int = 0,
) -> dict:
    """Query Google Places for amenity categories with monthly + session caps."""
    key = api_key or get_google_maps_api_key()
    if not key:
        return {
            "enabled": False,
            "source": "Google Places API (New)",
            "note": "Set GOOGLE_MAPS_API_KEY in .env or Streamlit secrets.",
            "categories": [],
            "overall_score": None,
            "places": [],
            "api_calls": 0,
        }

    needed = calls_per_amenity_fetch()
    ok, limit_msg = can_fetch_amenities(session_calls_used)
    if not ok:
        return {
            "enabled": False,
            "source": "Google Places API (New)",
            "note": limit_msg,
            "categories": [],
            "overall_score": None,
            "places": [],
            "api_calls": 0,
        }

    # Reserve all calls upfront — no Google request if cap would be exceeded
    reserved, reserve_msg = reserve_calls(needed, session_calls_used)
    if not reserved:
        return {
            "enabled": False,
            "source": "Google Places API (New)",
            "note": reserve_msg,
            "categories": [],
            "overall_score": None,
            "places": [],
            "api_calls": 0,
        }

    radius_meters = radius_miles * 1609.34
    places_by_type: dict[str, list[AmenityPlace]] = {t: [] for t, _ in AMENITY_CATEGORIES}
    api_calls = 0

    try:
        for batch in TYPE_BATCHES:
            raw = _search_nearby_batch(latitude, longitude, batch, radius_meters, key)
            api_calls += 1
            for item in raw:
                loc = item.get("location") or {}
                plat = loc.get("latitude")
                plon = loc.get("longitude")
                if plat is None or plon is None:
                    continue
                dist = _haversine_miles(latitude, longitude, plat, plon)
                if dist > radius_miles:
                    continue
                cat = _match_category(item.get("types"), item.get("primaryType"))
                if not cat:
                    continue
                name = (item.get("displayName") or {}).get("text") or "Unknown"
                places_by_type[cat].append(
                    AmenityPlace(
                        name=name,
                        latitude=plat,
                        longitude=plon,
                        place_type=cat,
                        distance_mi=round(dist, 2),
                        rating=item.get("rating"),
                    )
                )
    except Exception as exc:
        return {
            "enabled": False,
            "source": "Google Places API (New)",
            "note": f"Google Places request failed after reserving quota: {exc}",
            "categories": [],
            "overall_score": None,
            "places": [],
            "api_calls": api_calls,
        }

    categories: list[dict] = []
    all_places: list[AmenityPlace] = []
    for place_type, label in AMENITY_CATEGORIES:
        places = places_by_type[place_type]
        nearest = min((p.distance_mi for p in places), default=None)
        categories.append(
            {
                "type": place_type,
                "label": label,
                "count": len(places),
                "nearest_mi": nearest,
                "score": _category_score(len(places), nearest, radius_miles),
            }
        )
        all_places.extend(places)

    overall = round(sum(c["score"] for c in categories) / len(categories), 1) if categories else None

    return {
        "enabled": True,
        "source": "Google Places API (New) — returns lat/lon per place",
        "note": f"Used {api_calls} API call(s) this lookup ({calls_per_amenity_fetch()} max per new address).",
        "radius_miles": radius_miles,
        "categories": categories,
        "overall_score": overall,
        "places": all_places,
        "api_calls": api_calls,
    }
