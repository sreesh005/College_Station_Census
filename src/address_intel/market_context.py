"""County-level market context: home prices, HPI, crime rates."""

from __future__ import annotations

import io

import pandas as pd
import requests

from ..config import get_api_key

ZILLOW_COUNTY_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
FHFA_COUNTY_CSV_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_county.csv"
CDE_SUMMARIZED_URL = "https://api.usa.gov/crime/fbi/cde/summarized/state/{state_abbr}/{offense}"


def fetch_county_zillow(county_fips: str, state_abbr: str = "TX") -> dict:
    response = requests.get(ZILLOW_COUNTY_URL, timeout=180)
    response.raise_for_status()
    zhvi = pd.read_csv(io.StringIO(response.text), low_memory=False)
    zhvi = zhvi.copy()
    zhvi["county_fips"] = (
        zhvi["StateCodeFIPS"].astype(str).str.zfill(2)
        + zhvi["MunicipalCodeFIPS"].astype(str).str.zfill(3)
    )
    row = zhvi[zhvi["county_fips"] == county_fips]
    if row.empty:
        return {"source": "Zillow ZHVI", "note": f"No ZHVI row for {county_fips}"}

    date_cols = [c for c in row.columns if c[:4].isdigit() and "-" in c]
    latest_col = sorted(date_cols)[-1]
    value = row.iloc[0][latest_col]
    return {
        "zillow_zhvi": float(value) if pd.notna(value) else None,
        "zillow_zhvi_month": latest_col,
        "zillow_region_name": row.iloc[0].get("RegionName"),
        "source": "Zillow Home Value Index (county)",
        "note": None,
    }


def fetch_county_fhfa(county_fips: str) -> dict:
    """Latest annual FHFA HPI for a county (falls back gracefully)."""
    try:
        response = requests.get(FHFA_COUNTY_CSV_URL, timeout=180)
        if response.status_code != 200:
            raise RuntimeError("FHFA download failed")
        raw = response.text
        # FHFA county file is often Excel disguised as CSV; try both parsers.
        try:
            hpi = pd.read_csv(io.StringIO(raw), low_memory=False)
        except Exception:
            hpi = pd.read_excel(io.BytesIO(response.content), skiprows=5, header=None)
            hpi.columns = [
                "state",
                "county_name",
                "county_fips",
                "fhfa_hpi_year",
                "annual_change",
                "fhfa_hpi_index_nsa",
                "index_1990",
                "index_2000",
            ]
        if "county_fips" not in hpi.columns:
            # Wide CSV variant
            return {"source": "FHFA HPI", "note": "Unexpected FHFA file format"}
        hpi["county_fips"] = hpi["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        subset = hpi[hpi["county_fips"] == county_fips].copy()
        if subset.empty:
            return {"source": "FHFA HPI", "note": f"No FHFA row for {county_fips}"}
        subset["fhfa_hpi_year"] = pd.to_numeric(subset["fhfa_hpi_year"], errors="coerce")
        latest = subset.sort_values("fhfa_hpi_year", ascending=False).iloc[0]
        return {
            "fhfa_hpi_index": float(latest["fhfa_hpi_index_nsa"]),
            "fhfa_hpi_year": int(latest["fhfa_hpi_year"]),
            "fhfa_county_name": latest.get("county_name"),
            "source": "FHFA House Price Index (county)",
            "note": None,
        }
    except Exception as exc:
        return {"source": "FHFA HPI", "note": str(exc)}


def fetch_state_crime_rates(state_abbr: str = "TX") -> dict:
    """FBI Crime Data Explorer summarized state monthly rates."""
    api_key = get_api_key("DATA_GOV_API_KEY")
    if not api_key:
        return {"source": "FBI CDE", "note": "DATA_GOV_API_KEY not configured"}

    offenses: dict[str, float] = {}
    year_used = None
    for year in range(2023, 2019, -1):
        year_offenses: dict[str, float] = {}
        ok = True
        for offense in ("violent-crime", "property-crime", "burglary", "larceny"):
            url = CDE_SUMMARIZED_URL.format(state_abbr=state_abbr, offense=offense)
            response = requests.get(
                url,
                params={"api_key": api_key, "from": f"01-{year}", "to": f"12-{year}"},
                timeout=120,
            )
            if response.status_code != 200:
                ok = False
                break
            payload = response.json()
            rates = payload.get("offenses", {}).get("rates", {})
            state_key = next((k for k in rates if state_abbr in k or "Texas" in k), None)
            if not state_key:
                ok = False
                break
            monthly = rates[state_key]
            year_offenses[offense.replace("-", "_")] = sum(monthly.values()) / max(len(monthly), 1)
        if ok and year_offenses:
            offenses = year_offenses
            year_used = year
            break

    if not offenses:
        return {"source": "FBI CDE", "note": "FBI crime API unavailable"}

    return {
        "violent_crime_rate": offenses.get("violent_crime"),
        "property_crime_rate": offenses.get("property_crime"),
        "burglary_rate": offenses.get("burglary"),
        "larceny_rate": offenses.get("larceny"),
        "crime_data_year": year_used,
        "source": "FBI CDE (Texas state rate — county proxy)",
        "note": "State-level rate per 100K; use Dallas PD data for neighborhood counts.",
    }
