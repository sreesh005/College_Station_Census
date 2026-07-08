from __future__ import annotations

import re

import pandas as pd
import requests

from .config import RAW_DIR, get_api_key, load_pilot_config


def _fred_series_id(state_fips: str, county_fips: str) -> str:
    # FRED uses a leading zero: BPPRIV048113 for Dallas County, TX (48 + 113)
    return f"BPPRIV0{state_fips}{county_fips[-3:]}"


def fetch_building_permits() -> pd.DataFrame:
    cfg = load_pilot_config()
    api_key = get_api_key("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY is required. Copy .env.example to .env and add your key.")

    state_fips = cfg["state_fips"]
    records: list[dict] = []

    for county in cfg["counties"]:
        series_id = _fred_series_id(state_fips, county["fips"])
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        }
        response = requests.get(url, params=params, timeout=60)
        if response.status_code != 200:
            records.append(
                {
                    "county_fips": county["fips"],
                    "building_permits_latest": pd.NA,
                    "building_permits_year": pd.NA,
                    "fred_series_id": series_id,
                    "note": f"FRED error {response.status_code}",
                }
            )
            continue

        observations = response.json().get("observations", [])
        latest = next((o for o in observations if o.get("value") not in (".", None, "")), None)
        records.append(
            {
                "county_fips": county["fips"],
                "building_permits_latest": int(latest["value"]) if latest else pd.NA,
                "building_permits_year": int(latest["date"][:4]) if latest else pd.NA,
                "fred_series_id": series_id,
                "note": None,
            }
        )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "building_permits.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_building_permits().to_string(index=False))
