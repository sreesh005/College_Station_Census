from __future__ import annotations

import pandas as pd
import requests

FHWA_TX_QUERY_URL = (
    "https://geo.dot.gov/server/rest/services/Hosted/Texas_2018_PR/FeatureServer/0/query"
)

SAMPLE_COUNTY_TRAFFIC = {
    "county_fips": "48041",
    "hpms_segment_count": 842,
    "mean_aadt": 18_450,
    "max_aadt": 52_300,
    "p90_aadt": 38_200,
    "source": "offline sample",
}


def _aggregate_aadt(aadt_values: list[float]) -> dict:
    if not aadt_values:
        return {
            "hpms_segment_count": 0,
            "mean_aadt": None,
            "max_aadt": None,
            "p90_aadt": None,
        }
    series = pd.Series(aadt_values)
    return {
        "hpms_segment_count": len(series),
        "mean_aadt": round(series.mean(), 0),
        "max_aadt": int(series.max()),
        "p90_aadt": round(series.quantile(0.9), 0),
    }


def fetch_county_traffic(county_code: int) -> dict:
    """Aggregate FHWA HPMS AADT for an entire county."""
    aadt_values: list[float] = []
    offset = 0
    page_size = 2000

    try:
        while True:
            params = {
                "where": f"county_code={county_code} AND aadt>0",
                "outFields": "aadt",
                "resultRecordCount": page_size,
                "resultOffset": offset,
                "f": "json",
            }
            response = requests.get(FHWA_TX_QUERY_URL, params=params, timeout=60)
            response.raise_for_status()
            features = response.json().get("features", [])
            if not features:
                break

            for feat in features:
                val = feat.get("attributes", {}).get("aadt")
                if val is not None and val > 0:
                    aadt_values.append(float(val))

            if len(features) < page_size:
                break
            offset += page_size

        stats = _aggregate_aadt(aadt_values)
        stats["source"] = "FHWA HPMS (geo.dot.gov)"
        return stats
    except requests.RequestException:
        if county_code == 41:
            return dict(SAMPLE_COUNTY_TRAFFIC)
        return {"source": "unavailable"}


def fetch_nearby_traffic(
    latitude: float,
    longitude: float,
    radius_miles: float = 3.0,
) -> pd.DataFrame:
    """Fetch road segments with AADT within a radius of a point."""
    radius_meters = radius_miles * 1609.34
    max_records = min(100, max(20, int(radius_miles * 10)))

    params = {
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": radius_meters,
        "units": "esriSRUnit_Meter",
        "outFields": "route_id,route_name,route_number,aadt,f_system",
        "returnGeometry": "true",
        "outSR": 4326,
        "orderByFields": "aadt DESC",
        "resultRecordCount": max_records,
        "f": "json",
    }

    try:
        response = requests.get(FHWA_TX_QUERY_URL, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            return _sample_nearby_traffic(radius_miles)
        features = payload.get("features", [])
    except requests.RequestException:
        return _sample_nearby_traffic(radius_miles)

    rows = []
    for feat in features:
        attrs = feat.get("attributes", {})
        aadt = attrs.get("aadt")
        if aadt is None or aadt <= 0:
            continue
        row = {
            "route": _format_route(attrs),
            "aadt": int(aadt),
            "func_class": _func_class_label(attrs.get("f_system")),
        }
        lats, lons = _geometry_to_latlon(feat.get("geometry"))
        row["lats"] = lats
        row["lons"] = lons
        rows.append(row)

    if not rows:
        return _sample_nearby_traffic(radius_miles)

    df = pd.DataFrame(rows)
    return df.groupby("route", as_index=False).agg(
        {"aadt": "max", "func_class": "first", "lats": "first", "lons": "first"}
    ).sort_values("aadt", ascending=False).reset_index(drop=True)


def _geometry_to_latlon(geometry: dict | None) -> tuple[list[float], list[float]]:
    """Convert ArcGIS polyline geometry to lat/lon lists."""
    if not geometry or "paths" not in geometry:
        return [], []
    path = geometry["paths"][0]
    lons = [pt[0] for pt in path]
    lats = [pt[1] for pt in path]
    return lats, lons


def _sample_nearby_traffic(radius_miles: float = 3.0) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"route": "US 190 / University Dr", "aadt": 52300, "func_class": "Principal Arterial"},
            {"route": "SH 6 / Texas Ave", "aadt": 41200, "func_class": "Principal Arterial"},
            {"route": "FM 2818 / Harvey Rd", "aadt": 28500, "func_class": "Minor Arterial"},
            {"route": "FM 2154 / Wellborn Rd", "aadt": 22100, "func_class": "Minor Arterial"},
            {"route": "George Bush Dr", "aadt": 15800, "func_class": "Major Collector"},
        ]
    )
    df["note"] = f"Sample data (API unavailable) · {radius_miles:g} mi search"
    return df


def _format_route(attrs: dict) -> str:
    name = (attrs.get("route_name") or "").strip()
    number = attrs.get("route_number")
    if name and name not in ("-", "None"):
        return name
    if number is not None and str(number).strip():
        return f"Route {number}"
    return attrs.get("route_id") or "Unknown"


def _func_class_label(code: int | None) -> str:
    labels = {
        1: "Interstate",
        2: "Principal Arterial",
        3: "Minor Arterial",
        4: "Major Collector",
        5: "Minor Collector",
        6: "Local",
        7: "Local",
    }
    return labels.get(code, "Road") if code else "Road"
