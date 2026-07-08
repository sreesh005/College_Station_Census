from __future__ import annotations

import pandas as pd
import requests

from .config import RAW_DIR, get_api_key, load_pilot_config
from .fetch_offline import SAMPLE_CRIME

CDE_SUMMARIZED_URL = "https://api.usa.gov/crime/fbi/cde/summarized/state/{state_abbr}/{offense}"
LEGACY_ESTIMATES_URL = (
    "https://api.usa.gov/crime/fbi/sapi/api/estimates/states/{state_abbr}/{start_year}/{end_year}"
)


def _fetch_cde_state_rates(state_abbr: str, api_key: str, year: int) -> dict | None:
    offenses: dict[str, float] = {}
    for offense in ("violent-crime", "property-crime", "burglary", "larceny"):
        url = CDE_SUMMARIZED_URL.format(state_abbr=state_abbr, offense=offense)
        response = requests.get(
            url,
            params={"api_key": api_key, "from": f"01-{year}", "to": f"12-{year}"},
            timeout=120,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
        rates = payload.get("offenses", {}).get("rates", {})
        state_key = next((k for k in rates if state_abbr in k or "Texas" in k), None)
        if not state_key:
            continue
        monthly = rates[state_key]
        offenses[offense.replace("-", "_")] = sum(monthly.values()) / max(len(monthly), 1)

    if not offenses:
        return None

    return {
        "crime_data_year": year,
        "violent_crime_rate": offenses.get("violent_crime"),
        "property_crime_rate": offenses.get("property_crime"),
        "burglary_rate": offenses.get("burglary"),
        "larceny_rate": offenses.get("larceny"),
        "crime_source": "FBI CDE summarized (state monthly rates)",
    }


def _fetch_legacy_estimates(state_abbr: str, api_key: str, year: int) -> dict | None:
    url = LEGACY_ESTIMATES_URL.format(state_abbr=state_abbr, start_year=year, end_year=year)
    response = requests.get(url, params={"api_key": api_key}, timeout=120)
    if response.status_code != 200:
        return None
    results = response.json().get("results", [])
    if not results:
        return None
    latest = results[-1]
    return {
        "crime_data_year": int(latest.get("year", year)),
        "state_population": latest.get("population"),
        "violent_crime": latest.get("violent_crime"),
        "property_crime": latest.get("property_crime"),
        "burglary": latest.get("burglary"),
        "larceny": latest.get("larceny"),
        "crime_source": "FBI SAPI state estimates",
    }


def fetch_crime_state() -> pd.DataFrame:
    """State-level FBI crime data allocated to counties via ACS population."""
    cfg = load_pilot_config()
    api_key = get_api_key("DATA_GOV_API_KEY")
    if not api_key:
        raise RuntimeError("DATA_GOV_API_KEY is required (sign up at api.data.gov).")

    state_abbr = cfg["state_abbr"]
    state_data = None
    cde_rates = None
    for year in range(2023, 2019, -1):
        state_data = _fetch_legacy_estimates(state_abbr, api_key, year)
        if state_data:
            break

    if not state_data:
        for year in range(2023, 2019, -1):
            cde_rates = _fetch_cde_state_rates(state_abbr, api_key, year)
            if cde_rates:
                break

    if not state_data and not cde_rates:
        out = pd.DataFrame(SAMPLE_CRIME)
        out["note"] = "FBI Crime API unavailable; using bundled Texas state proxy"
        out.to_csv(RAW_DIR / "crime_state_proxy.csv", index=False)
        return out

    records = []
    for county in cfg["counties"]:
        row = {"county_fips": county["fips"]}
        if state_data:
            row.update({k: v for k, v in state_data.items() if k != "crime_source"})
            row["note"] = state_data["crime_source"]
        else:
            row.update(cde_rates)
            row["note"] = cde_rates["crime_source"]
        records.append(row)

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "crime_state_proxy.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_crime_state().to_string(index=False))
