from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, get_api_key, load_pilot_config

PEP_URL = "https://api.census.gov/data/2023/pep/charv"


def fetch_pep_county() -> pd.DataFrame:
    cfg = load_pilot_config()
    api_key = get_api_key("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError("CENSUS_API_KEY is required for Census PEP.")

    state_fips = cfg["state_fips"]
    pilot_fips = {c["fips"] for c in cfg["counties"]}
    records: list[dict] = []

    for county in cfg["counties"]:
        county_code = county["fips"][-3:]
        params = {
            "get": "POP",
            "for": f"county:{county_code}",
            "in": f"state:{state_fips}",
            "YEAR": 2023,
            "key": api_key,
        }
        response = requests.get(PEP_URL, params=params, timeout=120)
        response.raise_for_status()
        rows = response.json()
        pop = int(rows[1][0]) if len(rows) > 1 else pd.NA
        records.append(
            {
                "county_fips": county["fips"],
                "pep_population": pop,
                "pep_year": 2023,
                "note": None,
            }
        )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out = out[out["county_fips"].isin(pilot_fips)]
    out.to_csv(RAW_DIR / "pep_county.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_pep_county().to_string(index=False))
