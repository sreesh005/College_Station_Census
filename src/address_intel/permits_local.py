"""Dallas building permits and county-level permit indicators."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from ..config import get_api_key

DEFAULT_PERMITS_URL = "https://www.dallasopendata.com/resource/e7gq-4sah.json"

# Official Dallas Open Data metadata (dataset e7gq-4sah):
# "This permit data set is historical and no longer updated."
# Last portal update ~Aug 2020; issued_date spans mainly 2018–early 2020.
PERMITS_DATASET_NOTE = (
    "City of Dallas marks this open-data feed as **historical** (frozen ~2020). "
    "Current permits moved to the **DallasNow / Accela** portal — not in this API."
)


def classify_permit_land_use(land_use: str | None) -> str:
    """Broad category from Dallas permit land_use description."""
    if not land_use:
        return "Other"
    text = land_use.upper()
    if any(k in text for k in ("INDUSTRIAL", "MANUFACTUR", "WAREHOUSE", "DISTRIBUTION", "FACTORY")):
        return "Industrial"
    if any(
        k in text
        for k in (
            "SINGLE FAMILY",
            "MULTI-FAMILY",
            "MULTIFAMILY",
            "RESIDENTIAL",
            "DWELLING",
            "APARTMENT",
            "CONDOMINIUM",
            "TOWNHOME",
        )
    ):
        return "Residential"
    if any(
        k in text
        for k in (
            "COMMERCIAL",
            "RETAIL",
            "OFFICE",
            "RESTAURANT",
            "HOTEL",
            "BANK",
            "SERVICE",
            "MIXED",
        )
    ):
        return "Commercial"
    return "Other"


def _parse_issue_date(value: str | None) -> datetime | None:
    if not value or str(value).upper() == "NULL":
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(a))


def _parse_permit_location(row: dict) -> tuple[float | None, float | None]:
    for key in ("location_1", "location", "geocoded_column"):
        geo = row.get(key)
        if isinstance(geo, dict):
            try:
                return float(geo.get("latitude")), float(geo.get("longitude"))
            except (TypeError, ValueError):
                continue
    for lat_key, lon_key in (("latitude", "longitude"), ("lat", "lon")):
        try:
            return float(row.get(lat_key)), float(row.get(lon_key))
        except (TypeError, ValueError):
            continue
    return None, None


def _fetch_permit_rows(
    api_url: str,
    zip_clean: str,
    max_records: int,
) -> tuple[list[dict], str | None]:
    """Query Dallas permits API with fallbacks for picky SoQL parsing."""
    attempts: list[tuple[dict, str]] = [
        ({"$limit": max_records, "$where": f"zip_code='{zip_clean}'", "$order": "issued_date DESC"}, "zip+order"),
        ({"$limit": max_records, "$where": f"zip_code='{zip_clean}'"}, "zip"),
        ({"$limit": max_records, "$order": "issued_date DESC"}, "order-only"),
        ({"$limit": max_records}, "plain"),
    ]
    last_error: str | None = None
    for params, _label in attempts:
        try:
            response = requests.get(api_url, params=params, timeout=90)
            response.raise_for_status()
            rows = response.json()
            if zip_clean and _label in {"order-only", "plain"}:
                rows = [r for r in rows if str(r.get("zip_code") or "").strip()[:5] == zip_clean]
            return rows[:max_records], None
        except Exception as exc:
            last_error = str(exc)
    return [], last_error


def fetch_nearby_permits(
    latitude: float,
    longitude: float,
    radius_miles: float = 1.0,
    lookback_days: int = 365 * 10,
    zip_code: str | None = None,
    api_url: str = DEFAULT_PERMITS_URL,
    max_records: int = 2000,
) -> dict:
    """
    Dallas building permit activity near an address.

    The open-data feed has street addresses but usually no lat/lon, so we filter
    by ZIP code and summarize land_use categories (residential / commercial / industrial).
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    zip_clean = str(zip_code or "").strip()[:5]

    rows, fetch_error = _fetch_permit_rows(api_url, zip_clean, max_records)
    if fetch_error:
        return {
            "permit_count": 0,
            "zip_permit_count": 0,
            "permits": pd.DataFrame(),
            "land_use_breakdown": {},
            "category_breakdown": {},
            "lookback_days": lookback_days,
            "source": "Dallas Open Data (e7gq-4sah)",
            "note": f"Permit fetch failed: {fetch_error}",
        }

    filtered: list[dict] = []
    for row in rows:
        issued = _parse_issue_date(row.get("issued_date"))
        if issued and issued < since:
            continue
        row["_land_use_category"] = classify_permit_land_use(row.get("land_use"))
        lat, lon = _parse_permit_location(row)
        if lat is not None and lon is not None:
            row["_distance_mi"] = round(_haversine_miles(latitude, longitude, lat, lon), 2)
            if row["_distance_mi"] <= radius_miles:
                filtered.append(row)
        elif zip_clean:
            row["_distance_mi"] = None
            filtered.append(row)

    df = pd.DataFrame(filtered)
    land_use_breakdown = (
        df["land_use"].value_counts().head(8).to_dict() if not df.empty and "land_use" in df.columns else {}
    )
    category_breakdown = (
        df["_land_use_category"].value_counts().to_dict()
        if not df.empty and "_land_use_category" in df.columns
        else {}
    )

    scope = f"ZIP {zip_clean}" if zip_clean else f"{radius_miles:g} mi radius"
    return {
        "permit_count": len(filtered),
        "zip_permit_count": len(filtered),
        "radius_miles": radius_miles,
        "lookback_days": lookback_days,
        "permits": df,
        "land_use_breakdown": land_use_breakdown,
        "category_breakdown": category_breakdown,
        "source": "Dallas Open Data (Building Permits)",
        "note": (
            f"{PERMITS_DATASET_NOTE} Showing permits in {scope} from this archive "
            f"(typically 2018–2020)."
        ),
    }


def fetch_county_permit_series(county_fips: str, state_fips: str = "48") -> dict:
    """Latest FRED private-housing building permits for a county."""
    api_key = get_api_key("FRED_API_KEY")
    if not api_key:
        return {"source": "FRED", "note": "FRED_API_KEY not configured"}

    series_id = f"BPPRIV0{state_fips}{county_fips[-3:]}"
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 3,
    }
    response = requests.get(url, params=params, timeout=60)
    if response.status_code != 200:
        return {"fred_series_id": series_id, "source": "FRED", "note": f"FRED error {response.status_code}"}

    observations = response.json().get("observations", [])
    latest = next((o for o in observations if o.get("value") not in (".", None, "")), None)
    if not latest:
        return {"fred_series_id": series_id, "source": "FRED", "note": "No observations"}

    return {
        "building_permits_latest": int(latest["value"]),
        "building_permits_year": int(latest["date"][:4]),
        "fred_series_id": series_id,
        "source": "FRED (county private housing units permitted)",
        "note": None,
    }
