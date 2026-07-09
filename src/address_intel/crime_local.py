"""Dallas Police Department incident data (Socrata open data)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

DEFAULT_INCIDENTS_URL = "https://www.dallasopendata.com/resource/qv6i-rri7.json"

VIOLENT_KEYWORDS = (
    "ASSAULT",
    "HOMICIDE",
    "MURDER",
    "ROBBERY",
    "RAPE",
    "SEXUAL",
    "KIDNAPPING",
    "AGGRAVATED",
)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def _parse_geocoded(row: dict) -> tuple[float | None, float | None]:
    geo = row.get("geocoded_column") or {}
    if isinstance(geo, dict):
        try:
            return float(geo.get("latitude")), float(geo.get("longitude"))
        except (TypeError, ValueError):
            pass
    return None, None


def fetch_nearby_crime(
    latitude: float,
    longitude: float,
    radius_miles: float = 1.0,
    lookback_days: int = 365,
    zip_code: str | None = None,
    api_url: str = DEFAULT_INCIDENTS_URL,
    max_records: int = 5000,
) -> dict:
    """
    Count Dallas PD incidents near a point.

    Uses zip + date pre-filter on Socrata, then haversine distance in Python
    (more reliable than within_circle on nested geocoded columns).
    """
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT00:00:00")
    where_parts = [f"reporteddate > '{since}'"]
    if zip_code:
        where_parts.append(f"zip_code='{str(zip_code).strip()[:5]}'")

    params = {
        "$where": " AND ".join(where_parts),
        "$limit": max_records,
        "$select": "incidentnum,offincident,nibrs_crime_category,reporteddate,zip_code,geocoded_column",
        "$order": "reporteddate DESC",
    }
    response = requests.get(api_url, params=params, timeout=90)
    response.raise_for_status()
    rows = response.json()

    nearby: list[dict] = []
    for row in rows:
        lat, lon = _parse_geocoded(row)
        if lat is None or lon is None:
            continue
        dist = _haversine_miles(latitude, longitude, lat, lon)
        if dist <= radius_miles:
            row["_distance_mi"] = round(dist, 2)
            row["_latitude"] = lat
            row["_longitude"] = lon
            nearby.append(row)

    violent = sum(
        1
        for r in nearby
        if any(k in (r.get("offincident") or "").upper() for k in VIOLENT_KEYWORDS)
        or "ASSAULT" in (r.get("nibrs_crime_category") or "").upper()
    )
    property_crimes = sum(
        1
        for r in nearby
        if any(k in (r.get("offincident") or "").upper() for k in ("BURGLARY", "THEFT", "LARCENY", "ROBBERY"))
    )

    df = pd.DataFrame(nearby)
    top_types = (
        df["offincident"].value_counts().head(5).to_dict()
        if not df.empty and "offincident" in df.columns
        else {}
    )

    return {
        "incident_count": len(nearby),
        "violent_count": violent,
        "property_count": property_crimes,
        "lookback_days": lookback_days,
        "radius_miles": radius_miles,
        "top_offense_types": top_types,
        "incidents": df,
        "source": "Dallas PD Open Data (qv6i-rri7)",
        "note": (
            f"Based on up to {max_records} recent records"
            + (f" in ZIP {zip_code}" if zip_code else "")
            + "; city cautions against statistical comparisons."
        ),
    }
