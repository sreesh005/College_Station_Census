from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, get_api_key, load_pilot_config

ACS_VARIABLES = {
    "B01001_001E": "population",
    "B19013_001E": "median_household_income",
    "B11001_001E": "households",
    "B25077_001E": "median_home_value",
    "B08303_001E": "commuters_total",
    "B08303_013E": "commute_60_plus_min",
}


def _parse_census_response(response: requests.Response) -> list:
    if "Invalid Key" in response.text or "Missing Key" in response.text:
        raise RuntimeError(
            "Census API rejected CENSUS_API_KEY. Common fixes: "
            "(1) use a key from https://api.census.gov/data/key_signup.html (not api.data.gov), "
            "(2) click the activation link in the Census Bureau email, "
            "(3) wait up to 24 hours after activation. "
            "Test in a browser: api.census.gov/data/2023/acs/acs5?get=NAME&for=us:1&key=YOUR_KEY"
        )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Census API returned non-JSON response: {response.text[:200]}") from exc


def fetch_acs_county() -> pd.DataFrame:
    cfg = load_pilot_config()
    api_key = get_api_key("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError("CENSUS_API_KEY is required. Copy .env.example to .env and add your key.")

    state_fips = cfg["state_fips"]
    pilot_fips = {c["fips"] for c in cfg["counties"]}
    var_list = ",".join(["NAME", *ACS_VARIABLES.keys()])

    vintages = [cfg["acs_vintage"], "2023", "2022"]
    rows = None
    vintage_used = None
    last_error = None

    for vintage in dict.fromkeys(vintages):
        url = f"https://api.census.gov/data/{vintage}/acs/acs5"
        params = {
            "get": var_list,
            "for": "county:*",
            "in": f"state:{state_fips}",
            "key": api_key,
        }
        response = requests.get(url, params=params, timeout=120)
        try:
            rows = _parse_census_response(response)
            vintage_used = vintage
            break
        except RuntimeError as exc:
            last_error = exc
            if "Invalid Key" in str(exc) or "Missing Key" in str(exc):
                raise

    if rows is None:
        raise RuntimeError(str(last_error or "Unable to fetch ACS data"))

    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["county_fips"] = (df["state"] + df["county"]).astype(str).str.zfill(5)
    df = df[df["county_fips"].isin(pilot_fips)].copy()

    rename = {code: label for code, label in ACS_VARIABLES.items()}
    rename["NAME"] = "county_name"
    df = df.rename(columns=rename)

    for col in ACS_VARIABLES.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["commute_60_plus_pct"] = (
        df["commute_60_plus_min"] / df["commuters_total"].replace(0, pd.NA)
    ) * 100

    keep = [
        "county_fips",
        "county_name",
        "population",
        "median_household_income",
        "households",
        "median_home_value",
        "commuters_total",
        "commute_60_plus_min",
        "commute_60_plus_pct",
    ]
    out = df[keep].copy()
    out["acs_vintage"] = vintage_used
    out.to_csv(RAW_DIR / "acs_county.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_acs_county().to_string(index=False))
