from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, get_api_key, load_pilot_config
from .fetch_acs import _parse_census_response


def fetch_cbp() -> pd.DataFrame:
    cfg = load_pilot_config()
    api_key = get_api_key("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError("CENSUS_API_KEY is required.")

    vintage = cfg["cbp_vintage"]
    state_fips = cfg["state_fips"]
    pilot_fips = {c["fips"] for c in cfg["counties"]}

    url = f"https://api.census.gov/data/{vintage}/cbp"
    params = {
        "get": "NAME,NAICS2017,ESTAB,EMP,PAYANN",
        "for": "county:*",
        "in": f"state:{state_fips}",
        "NAICS2017": "00",
        "key": api_key,
    }
    response = requests.get(url, params=params, timeout=120)
    rows = _parse_census_response(response)
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["county_fips"] = df["state"] + df["county"]
    df = df[df["county_fips"].isin(pilot_fips)].copy()

    for col in ("ESTAB", "EMP", "PAYANN"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    total = df.rename(
        columns={"ESTAB": "total_establishments", "EMP": "total_employment", "PAYANN": "total_annual_payroll"}
    )[["county_fips", "total_establishments", "total_employment", "total_annual_payroll"]]

    params["NAICS2017"] = "44-45"
    response = requests.get(url, params=params, timeout=120)
    rows = _parse_census_response(response)
    retail = pd.DataFrame(rows[1:], columns=rows[0])
    retail["county_fips"] = retail["state"] + retail["county"]
    retail = retail[retail["county_fips"].isin(pilot_fips)].copy()
    retail["retail_establishments"] = pd.to_numeric(retail["ESTAB"], errors="coerce")
    retail["retail_employment"] = pd.to_numeric(retail["EMP"], errors="coerce")
    retail = retail[["county_fips", "retail_establishments", "retail_employment"]]

    out = total.merge(retail, on="county_fips", how="left")
    out["cbp_vintage"] = vintage
    out.to_csv(RAW_DIR / "cbp_county.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_cbp().to_string(index=False))
