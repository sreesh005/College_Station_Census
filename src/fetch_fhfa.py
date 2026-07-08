from __future__ import annotations

import io

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

FHFA_COUNTY_XLSX_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_county.csv"
FHFA_MASTER_CSV_URL = "https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv"


def _fetch_county_hpi_from_xlsx(pilot_fips: set[str], state_fips: str) -> pd.DataFrame | None:
    response = requests.get(FHFA_COUNTY_XLSX_URL, timeout=180)
    if response.status_code != 200:
        return None

    county = pd.read_excel(io.BytesIO(response.content), skiprows=5, header=None)
    county.columns = [
        "state",
        "county_name",
        "county_fips",
        "fhfa_hpi_year",
        "annual_change",
        "fhfa_hpi_index_nsa",
        "index_1990",
        "index_2000",
    ]
    county["county_fips"] = (
        county["county_fips"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    )
    county = county[county["county_fips"].str.startswith(state_fips)]
    county = county[county["county_fips"].isin(pilot_fips)]
    county["fhfa_hpi_year"] = pd.to_numeric(county["fhfa_hpi_year"], errors="coerce")
    county["fhfa_hpi_index_nsa"] = pd.to_numeric(county["fhfa_hpi_index_nsa"], errors="coerce")

    if county.empty:
        return None

    latest = (
        county.sort_values(["county_fips", "fhfa_hpi_year"], ascending=[True, False])
        .groupby("county_fips", as_index=False)
        .first()
    )

    return pd.DataFrame(
        {
            "county_fips": latest["county_fips"],
            "fhfa_place_name": latest["county_name"],
            "fhfa_hpi_year": latest["fhfa_hpi_year"],
            "fhfa_hpi_index_nsa": latest["fhfa_hpi_index_nsa"],
            "fhfa_hpi_index_sa": pd.NA,
            "note": "FHFA annual county XLSX",
        }
    )


def _fetch_state_proxy_hpi(cfg: dict, pilot_fips: set[str]) -> pd.DataFrame:
    response = requests.get(FHFA_MASTER_CSV_URL, timeout=180)
    response.raise_for_status()
    hpi = pd.read_csv(io.StringIO(response.text), low_memory=False)

    tx = hpi[
        (hpi["level"] == "State")
        & (hpi["place_name"].str.contains(cfg["state_abbr"], na=False) | hpi["place_name"].str.contains("Texas", na=False))
        & (hpi["hpi_flavor"] == "all-transactions")
        & (hpi["frequency"] == "quarterly")
    ].sort_values(["yr", "period"], ascending=[True, True])

    latest = tx.iloc[-1]
    return pd.DataFrame(
        {
            "county_fips": sorted(pilot_fips),
            "fhfa_place_name": "Texas (state proxy)",
            "fhfa_hpi_year": latest["yr"],
            "fhfa_hpi_index_nsa": latest["index_nsa"],
            "fhfa_hpi_index_sa": latest.get("index_sa", pd.NA),
            "note": "FHFA state-level proxy; county XLSX unavailable",
        }
    )


def fetch_fhfa_hpi() -> pd.DataFrame:
    cfg = load_pilot_config()
    state_fips = cfg["state_fips"]
    pilot_fips = {c["fips"] for c in cfg["counties"]}

    out = _fetch_county_hpi_from_xlsx(pilot_fips, state_fips)
    if out is None or out.empty:
        out = _fetch_state_proxy_hpi(cfg, pilot_fips)

    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "fhfa_hpi.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_fhfa_hpi().to_string(index=False))
