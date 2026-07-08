from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

NTAD_COUNTY_SUMMARY_URL = "https://data.transportation.gov/resource/8j5p-a5aj.json"


def fetch_ntad_traffic() -> pd.DataFrame:
    """BTS NTAD HPMS county summary — public road system length by county."""
    cfg = load_pilot_config()
    state_fips = cfg["state_fips"]
    records: list[dict] = []

    for county in cfg["counties"]:
        county_id = county["fips"][-3:]
        params = {
            "$select": "sum(systemlength) as total_system_miles",
            "$where": f"stateid='{state_fips}' AND countyid='{county_id}' AND datayear='2023'",
        }
        response = requests.get(NTAD_COUNTY_SUMMARY_URL, params=params, timeout=180)
        if response.status_code != 200:
            records.append(
                {
                    "county_fips": county["fips"],
                    "ntad_system_miles": pd.NA,
                    "ntad_year": 2023,
                    "note": f"BTS NTAD error {response.status_code}",
                }
            )
            continue

        payload = response.json()
        miles = float(payload[0]["total_system_miles"]) if payload else pd.NA
        records.append(
            {
                "county_fips": county["fips"],
                "ntad_system_miles": miles,
                "ntad_year": 2023,
                "note": None,
            }
        )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "ntad_traffic.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_ntad_traffic().to_string(index=False))
