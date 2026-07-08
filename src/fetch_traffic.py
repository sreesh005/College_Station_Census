from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

FHWA_TX_QUERY_URL = (
    "https://geo.dot.gov/server/rest/services/Hosted/Texas_2018_PR/FeatureServer/0/query"
)


def _fetch_hpms_aadt_for_county(county_code: int) -> list[float]:
    aadt_values: list[float] = []
    offset = 0
    page_size = 2000

    while True:
        params = {
            "where": f"county_code={county_code} AND aadt>0",
            "outFields": "aadt",
            "resultRecordCount": page_size,
            "resultOffset": offset,
            "f": "json",
        }
        response = requests.get(FHWA_TX_QUERY_URL, params=params, timeout=120)
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

    return aadt_values


def _aggregate_aadt(aadt_values: list[float]) -> dict:
    if not aadt_values:
        return {
            "hpms_segment_count": 0,
            "mean_aadt": pd.NA,
            "max_aadt": pd.NA,
            "p90_aadt": pd.NA,
            "total_aadt": pd.NA,
        }
    series = pd.Series(aadt_values)
    return {
        "hpms_segment_count": len(series),
        "mean_aadt": round(series.mean(), 1),
        "max_aadt": int(series.max()),
        "p90_aadt": round(series.quantile(0.9), 1),
        "total_aadt": int(series.sum()),
    }


def fetch_traffic() -> pd.DataFrame:
    cfg = load_pilot_config()
    records: list[dict] = []

    for county in cfg["counties"]:
        county_code = int(county["fips"][-3:])
        try:
            aadt_values = _fetch_hpms_aadt_for_county(county_code)
            stats = _aggregate_aadt(aadt_values)
            records.append(
                {
                    "county_fips": county["fips"],
                    **stats,
                    "note": "FHWA HPMS ArcGIS (geo.dot.gov)" if stats["hpms_segment_count"] else "No HPMS segments found",
                }
            )
        except requests.RequestException as exc:
            records.append(
                {
                    "county_fips": county["fips"],
                    "hpms_segment_count": pd.NA,
                    "mean_aadt": pd.NA,
                    "max_aadt": pd.NA,
                    "p90_aadt": pd.NA,
                    "total_aadt": pd.NA,
                    "note": f"FHWA HPMS error: {exc}",
                }
            )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "traffic_county.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_traffic().to_string(index=False))
