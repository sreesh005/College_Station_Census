"""City of Dallas base zoning lookup via ArcGIS REST."""

from __future__ import annotations

import re

import requests

DEFAULT_ZONING_LAYER = (
    "https://egis.dallascityhall.com/arcgis/rest/services/Sdc_public/Zoning/MapServer/15"
)


def classify_zoning(zone_code: str | None) -> str:
    """Map Dallas zoning district codes to broad land-use categories."""
    if not zone_code:
        return "Unknown"
    code = zone_code.upper().strip()
    # Check longer prefixes first (IM before I, CA before C, etc.)
    if re.match(r"^(IM|LI|IR|IP|I[\-\d])", code):
        return "Industrial"
    if re.match(r"^(MU|PD|UC|MC)", code):
        return "Mixed Use"
    if re.match(r"^(R|RD|RS|RE|RR|MH|TH|D[\-\d])", code):
        return "Residential"
    if re.match(r"^(CA|CB|CC|CR|NS|NO|C[\-\d]|O[\-\d]|LO)", code):
        return "Commercial"
    if code.startswith("I"):
        return "Industrial"
    if code.startswith(("C", "O")):
        return "Commercial"
    if code.startswith("R"):
        return "Residential"
    return "Other"


def fetch_zoning(
    latitude: float,
    longitude: float,
    map_server_url: str = DEFAULT_ZONING_LAYER,
) -> dict:
    """Point-in-polygon query against Dallas Base Zoning layer."""
    params = {
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "LONG_ZONE_DIST,ZONE_DIST",
        "returnGeometry": "false",
        "f": "json",
    }
    response = requests.get(f"{map_server_url}/query", params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()

    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message", "Zoning query failed"))

    features = payload.get("features") or []
    if not features:
        return {
            "zone_code": None,
            "zone_label": None,
            "land_use_category": "Unknown",
            "source": "City of Dallas GIS (Base Zoning)",
            "note": "No zoning polygon found — address may be outside Dallas city limits.",
        }

    attrs = features[0].get("attributes", {})
    zone_code = attrs.get("LONG_ZONE_DIST") or attrs.get("ZONE_DIST")
    category = classify_zoning(zone_code)
    return {
        "zone_code": zone_code,
        "zone_label": zone_code,
        "land_use_category": category,
        "source": "City of Dallas GIS (Base Zoning)",
        "note": None,
    }
