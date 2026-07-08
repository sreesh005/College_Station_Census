from __future__ import annotations

import json

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

BLM_LEASES_URL = (
    "https://gis.blm.gov/nlsdb/rest/services/HUB/BLM_Natl_MLRS_Oil_and_Gas_Leases/FeatureServer/0/query"
)


def _count_leases_in_envelope(xmin: float, ymin: float, xmax: float, ymax: float) -> tuple[int, float]:
    geometry = {
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "spatialReference": {"wkid": 4326},
    }
    params = {
        "where": "GEO_STATE='TX'",
        "geometry": json.dumps(geometry),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outStatistics": json.dumps(
            [
                {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "lease_count"},
                {"statisticType": "sum", "onStatisticField": "RCRD_ACRS", "outStatisticFieldName": "lease_acres"},
            ]
        ),
        "f": "json",
    }
    response = requests.get(BLM_LEASES_URL, params=params, timeout=120)
    response.raise_for_status()
    attrs = response.json().get("features", [{}])[0].get("attributes", {})
    return int(attrs.get("lease_count", 0) or 0), float(attrs.get("lease_acres", 0) or 0)


# Approximate county bounding boxes (WGS84) for DFW pilot counties.
COUNTY_BBOX: dict[str, tuple[float, float, float, float]] = {
    "48085": (-96.95, 33.00, -96.25, 33.55),  # Collin
    "48113": (-97.05, 32.55, -96.45, 33.05),  # Dallas
    "48121": (-97.55, 33.00, -96.85, 33.55),  # Denton
    "48397": (-96.55, 32.85, -96.25, 33.05),  # Rockwall
    "48439": (-97.55, 32.55, -97.00, 33.05),  # Tarrant
}


def fetch_blm_leases() -> pd.DataFrame:
    cfg = load_pilot_config()
    records: list[dict] = []

    for county in cfg["counties"]:
        fips = county["fips"]
        bbox = COUNTY_BBOX.get(fips)
        if not bbox:
            records.append(
                {
                    "county_fips": fips,
                    "blm_lease_count": pd.NA,
                    "blm_lease_acres": pd.NA,
                    "note": "No bbox configured",
                }
            )
            continue

        try:
            lease_count, lease_acres = _count_leases_in_envelope(*bbox)
            records.append(
                {
                    "county_fips": fips,
                    "blm_lease_count": lease_count,
                    "blm_lease_acres": round(lease_acres, 1),
                    "note": "BLM MLRS spatial query (TX leases in county bbox)",
                }
            )
        except requests.RequestException as exc:
            records.append(
                {
                    "county_fips": fips,
                    "blm_lease_count": pd.NA,
                    "blm_lease_acres": pd.NA,
                    "note": f"BLM MLRS error: {exc}",
                }
            )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "blm_leases.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_blm_leases().to_string(index=False))
