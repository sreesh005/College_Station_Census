from __future__ import annotations

import pandas as pd
import requests

from ..config import get_api_key

# Census ACS uses negative sentinel codes when an estimate is unavailable or suppressed.
# See: https://www.census.gov/programs-surveys/acs/technical-documentation/code-lists.html
def _sanitize_acs_value(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric) or numeric < 0:
        return None
    return numeric


ACS_VARIABLES = {
    "B01001_001E": "population",
    "B01002_001E": "median_age",
    "B19013_001E": "median_household_income",
    "B11001_001E": "households",
    "B25077_001E": "median_home_value",
    "B25003_001E": "housing_units_total",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    "B08303_001E": "commuters_total",
    "B08303_013E": "commute_60_plus_min",
    "B15003_001E": "education_universe",
    "B15003_022E": "bachelors_degree",
    "B15003_023E": "masters_degree",
}

# Public ACS 5-year estimates for Brazos County (48041), used when no API key.
SAMPLE_COUNTY_ACS = {
    "county_fips": "48041",
    "county_name": "Brazos County, Texas",
    "population": 237_980,
    "median_age": 25.8,
    "median_household_income": 52_141,
    "households": 83_412,
    "median_home_value": 248_900,
    "housing_units_total": 95_200,
    "owner_occupied": 38_500,
    "renter_occupied": 44_900,
    "commuters_total": 98_000,
    "commute_60_plus_min": 8_820,
    "education_universe": 145_000,
    "bachelors_degree": 42_000,
    "masters_degree": 18_500,
    "acs_vintage": "2023 (sample)",
    "source": "offline sample",
}


def _parse_census_response(response: requests.Response) -> list:
    if "Invalid Key" in response.text or "Missing Key" in response.text:
        raise RuntimeError("Census API key rejected")
    response.raise_for_status()
    return response.json()


def _fetch_acs(
    geography_for: str,
    geography_in: str,
    vintage: str = "2023",
) -> dict:
    api_key = get_api_key("CENSUS_API_KEY")
    if not api_key:
        return {}

    var_list = ",".join(["NAME", *ACS_VARIABLES.keys()])
    url = f"https://api.census.gov/data/{vintage}/acs/acs5"
    params = {
        "get": var_list,
        "for": geography_for,
        "in": geography_in,
        "key": api_key,
    }

    for v in dict.fromkeys([vintage, "2023", "2022"]):
        params_v = {**params}
        url_v = f"https://api.census.gov/data/{v}/acs/acs5"
        response = requests.get(url_v, params=params_v, timeout=60)
        try:
            rows = _parse_census_response(response)
            break
        except RuntimeError:
            raise
        except requests.RequestException:
            continue
    else:
        return {}

    if len(rows) < 2:
        return {}

    record = dict(zip(rows[0], rows[1]))
    out = {"name": record.get("NAME", ""), "acs_vintage": v, "source": "Census ACS 5-Year"}

    for code, label in ACS_VARIABLES.items():
        out[label] = _sanitize_acs_value(record.get(code))

    _add_derived_fields(out)
    return out


def _add_derived_fields(data: dict) -> None:
    commuters = data.get("commuters_total")
    long_commute = data.get("commute_60_plus_min")
    if commuters and commuters > 0 and long_commute is not None:
        data["commute_60_plus_pct"] = round(long_commute / commuters * 100, 1)

    housing = data.get("housing_units_total")
    owner = data.get("owner_occupied")
    renter = data.get("renter_occupied")
    if housing and housing > 0:
        if owner is not None:
            data["owner_occupied_pct"] = round(owner / housing * 100, 1)
        if renter is not None:
            data["renter_occupied_pct"] = round(renter / housing * 100, 1)

    edu_univ = data.get("education_universe")
    bachelors = data.get("bachelors_degree")
    masters = data.get("masters_degree")
    if edu_univ and edu_univ > 0:
        if bachelors is not None:
            data["bachelors_pct"] = round(bachelors / edu_univ * 100, 1)
        if masters is not None:
            data["masters_pct"] = round(masters / edu_univ * 100, 1)
        if bachelors is not None and masters is not None:
            data["college_plus_pct"] = round((bachelors + masters) / edu_univ * 100, 1)


def clean_acs_record(data: dict) -> dict:
    """Re-sanitize ACS numeric fields (handles cached sentinel values)."""
    out = dict(data)
    for label in ACS_VARIABLES.values():
        if label in out:
            out[label] = _sanitize_acs_value(out[label])
    _add_derived_fields(out)
    return out


def fetch_tract_acs(state_fips: str, county_code: str, tract_code: str, vintage: str = "2023") -> dict:
    """Fetch ACS demographics for a single census tract."""
    county_code = county_code.zfill(3)
    tract_code = tract_code.zfill(6)
    geography_in = f"state:{state_fips}+county:{county_code}"
    geography_for = f"tract:{tract_code}"

    data = _fetch_acs(geography_for, geography_in, vintage)
    if data:
        data["tract_fips"] = f"{state_fips}{county_code}{tract_code}"
        return clean_acs_record(data)

    return clean_acs_record(_sample_tract_data(state_fips, county_code, tract_code))


def fetch_county_acs(county_fips: str, vintage: str = "2023") -> dict:
    """Fetch ACS demographics for a county."""
    county_fips = county_fips.zfill(5)
    state_fips = county_fips[:2]
    county_code = county_fips[2:]

    data = _fetch_acs(f"county:{county_code}", f"state:{state_fips}", vintage)

    if data:
        data["county_fips"] = county_fips
        data["county_name"] = data.get("name", "")
        return clean_acs_record(data)

    if county_fips == "48041":
        return clean_acs_record(dict(SAMPLE_COUNTY_ACS))
    return {}


def _sample_tract_data(state_fips: str, county_code: str, tract_code: str) -> dict:
    """Scale county sample to tract-level placeholder when API unavailable."""
    base = dict(SAMPLE_COUNTY_ACS)
    # Tracts typically hold ~1-5% of county population; use tract code hash for variation
    seed = int(tract_code) % 100
    scale = 0.008 + (seed / 10000)
    out = {
        "tract_fips": f"{state_fips}{county_code}{tract_code}",
        "name": f"Census Tract {tract_code.lstrip('0') or tract_code}, Brazos County, Texas",
        "acs_vintage": "2023 (sample)",
        "source": "offline sample (tract estimate)",
    }
    for key in ACS_VARIABLES.values():
        if key in base and base[key] is not None:
            val = base[key]
            if isinstance(val, (int, float)) and key not in ("median_age", "median_household_income", "median_home_value"):
                out[key] = int(val * scale) if key != "median_age" else val
            else:
                jitter = 1 + (seed - 50) / 200
                out[key] = round(val * jitter, 1) if isinstance(val, float) else int(val * jitter)
    _add_derived_fields(out)
    return out
