from __future__ import annotations

import pandas as pd
import requests

from ..address_intel.census import _add_derived_fields, _sanitize_acs_value
from ..address_intel.traffic import fetch_nearby_traffic
from ..config import get_api_key

TIGER_TRACTS_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
)

TRACT_ACS_VARIABLES = {
    "B01001_001E": "population",
    "B01002_001E": "median_age",
    "B19013_001E": "median_household_income",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    "B15003_001E": "education_universe",
    "B15003_022E": "bachelors_degree",
    "B15003_023E": "masters_degree",
    "B08201_001E": "vehicle_universe",
    "B08201_002E": "vehicles_none",
    "B08201_003E": "vehicles_1",
    "B08201_004E": "vehicles_2",
    "B08201_005E": "vehicles_3",
    "B08201_006E": "vehicles_4_plus",
}


def fetch_tract_centroids(state_fips: str, county_code: str) -> pd.DataFrame:
    """Fetch census tract centroids from Census TIGERweb."""
    params = {
        "where": f"STATE='{state_fips}' AND COUNTY='{county_code}'",
        "outFields": "GEOID,NAME,CENTLAT,CENTLON",
        "returnGeometry": "false",
        "resultRecordCount": 2000,
        "f": "json",
    }
    response = requests.get(TIGER_TRACTS_URL, params=params, timeout=60)
    response.raise_for_status()
    features = response.json().get("features", [])
    rows = []
    for feat in features:
        attrs = feat["attributes"]
        geoid = str(attrs["GEOID"]).zfill(11)
        rows.append(
            {
                "tract_fips": geoid,
                "tract_name": attrs.get("NAME", ""),
                "latitude": float(str(attrs["CENTLAT"]).lstrip("+")),
                "longitude": float(str(attrs["CENTLON"]).lstrip("+")),
                "tract_code": geoid[5:],
            }
        )
    return pd.DataFrame(rows)


def fetch_all_tract_acs(state_fips: str, county_code: str, vintage: str = "2023") -> pd.DataFrame:
    """Batch-fetch ACS metrics for every tract in a county."""
    api_key = get_api_key("CENSUS_API_KEY")
    if not api_key:
        return pd.DataFrame()

    county_code = county_code.zfill(3)
    var_list = ",".join(["NAME", *TRACT_ACS_VARIABLES.keys()])
    rows = None
    vintage_used = vintage

    for v in dict.fromkeys([vintage, "2023", "2022"]):
        url = f"https://api.census.gov/data/{v}/acs/acs5"
        params = {
            "get": var_list,
            "for": "tract:*",
            "in": f"state:{state_fips}+county:{county_code}",
            "key": api_key,
        }
        response = requests.get(url, params=params, timeout=120)
        if response.status_code != 200:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        if len(payload) < 2:
            continue
        rows = payload
        vintage_used = v
        break

    if not rows:
        return pd.DataFrame()

    header, *data_rows = rows
    records = []
    for row in data_rows:
        record = dict(zip(header, row))
        tract_code = str(record["tract"]).zfill(6)
        out = {
            "tract_fips": f"{state_fips}{county_code}{tract_code}",
            "tract_code": tract_code,
            "name": record.get("NAME", ""),
            "acs_vintage": vintage_used,
        }
        for code, label in TRACT_ACS_VARIABLES.items():
            out[label] = _sanitize_acs_value(record.get(code))

        _add_vehicle_fields(out)
        _add_derived_fields(out)
        records.append(out)

    return pd.DataFrame(records)


def _add_vehicle_fields(data: dict) -> None:
    universe = data.get("vehicle_universe")
    if not universe or universe <= 0:
        return
    two_plus = sum(data.get(k) or 0 for k in ("vehicles_2", "vehicles_3", "vehicles_4_plus"))
    none = data.get("vehicles_none") or 0
    data["pct_2plus_vehicles"] = round(two_plus / universe * 100, 1)
    data["pct_no_vehicle"] = round(none / universe * 100, 1)


def _nearby_max_aadt(latitude: float, longitude: float, radius_miles: float = 1.5) -> float | None:
    nearby = fetch_nearby_traffic(latitude, longitude, radius_miles)
    if nearby.empty:
        return None
    return float(nearby["aadt"].max())


def build_tract_scorecard(
    state_fips: str,
    county_code: str,
    *,
    traffic_radius_miles: float = 1.5,
    progress_callback=None,
) -> pd.DataFrame:
    """Build a full metric table for every tract in the county."""
    centroids = fetch_tract_centroids(state_fips, county_code)
    acs = fetch_all_tract_acs(state_fips, county_code)

    if acs.empty:
        raise RuntimeError(
            "Could not fetch tract ACS data. Add CENSUS_API_KEY to .env for site selection."
        )

    df = centroids.merge(acs, on="tract_fips", how="inner", suffixes=("", "_acs"))

    aadt_values: list[float | None] = []
    total = len(df)
    for i, row in df.iterrows():
        if progress_callback:
            progress_callback((len(aadt_values) + 1) / total)
        aadt_values.append(_nearby_max_aadt(row["latitude"], row["longitude"], traffic_radius_miles))

    df["nearby_max_aadt"] = aadt_values
    df = df.copy()
    name_col = df["name"] if "name" in df.columns else ""
    df["tract_label"] = df["tract_name"].fillna(name_col)
    return df.reset_index(drop=True)
