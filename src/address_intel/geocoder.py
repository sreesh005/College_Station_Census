from __future__ import annotations

from dataclasses import dataclass

import requests

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"


@dataclass
class GeocodeResult:
    input_address: str
    matched_address: str
    latitude: float
    longitude: float
    county_fips: str
    county_name: str
    tract_fips: str
    tract_name: str
    block_group: str
    state_fips: str

    @property
    def tract_code(self) -> str:
        """6-digit tract code within the county."""
        return self.tract_fips[-6:] if self.tract_fips else ""


def geocode_address(address: str) -> GeocodeResult:
    """Geocode a US address via the free Census Bureau geocoder."""
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    response = requests.get(GEOCODER_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    matches = payload.get("result", {}).get("addressMatches", [])
    if not matches:
        raise ValueError(f"No match found for address: {address}")

    match = matches[0]
    coords = match["coordinates"]
    geographies = match.get("geographies", {})

    counties = geographies.get("Counties", [{}])
    tracts = geographies.get("Census Tracts", [{}])
    block_groups = geographies.get("Census Block Groups", [{}])

    county = counties[0] if counties else {}
    tract = tracts[0] if tracts else {}
    bg = block_groups[0] if block_groups else {}

    state_fips = str(county.get("STATE", tract.get("STATE", ""))).zfill(2)
    county_code = str(county.get("COUNTY", tract.get("COUNTY", ""))).zfill(3)
    tract_code = str(tract.get("TRACT", "")).zfill(6)

    return GeocodeResult(
        input_address=address,
        matched_address=match.get("matchedAddress", address),
        latitude=float(coords["y"]),
        longitude=float(coords["x"]),
        county_fips=f"{state_fips}{county_code}",
        county_name=county.get("NAME", "Unknown County"),
        tract_fips=f"{state_fips}{county_code}{tract_code}",
        tract_name=tract.get("NAME", "Unknown Tract"),
        block_group=bg.get("NAME", ""),
        state_fips=state_fips,
    )
