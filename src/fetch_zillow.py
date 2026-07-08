from __future__ import annotations

import io

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

ZILLOW_COUNTY_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)


def fetch_zillow_zhvi() -> pd.DataFrame:
    cfg = load_pilot_config()
    state_abbr = cfg["state_abbr"]
    pilot_fips = {c["fips"] for c in cfg["counties"]}

    response = requests.get(ZILLOW_COUNTY_URL, timeout=180)
    response.raise_for_status()
    zhvi = pd.read_csv(io.StringIO(response.text), low_memory=False)

    zhvi = zhvi[(zhvi["State"] == state_abbr) & (zhvi["RegionType"] == "county")].copy()
    zhvi["county_fips"] = (
        zhvi["StateCodeFIPS"].astype(str).str.zfill(2)
        + zhvi["MunicipalCodeFIPS"].astype(str).str.zfill(3)
    )
    zhvi = zhvi[zhvi["county_fips"].isin(pilot_fips)]

    date_cols = [c for c in zhvi.columns if c[0:4].isdigit() and "-" in c]
    latest_col = sorted(date_cols)[-1] if date_cols else None

    out = pd.DataFrame(
        {
            "county_fips": zhvi["county_fips"],
            "zillow_region_name": zhvi["RegionName"],
            "zillow_zhvi": zhvi[latest_col] if latest_col else pd.NA,
            "zillow_zhvi_month": latest_col,
            "note": None,
        }
    )
    out.to_csv(RAW_DIR / "zillow_zhvi.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_zillow_zhvi().to_string(index=False))
