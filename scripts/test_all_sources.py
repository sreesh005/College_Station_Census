"""Run fetchers and print a pass/fail matrix for all 9 data sources."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import RAW_DIR, ensure_dirs, missing_api_keys  # noqa: E402

FETCHERS = [
    ("Census ACS (api.census.gov acs/acs5)", "acs_county.csv", "src.fetch_acs", "fetch_acs_county"),
    ("Census PEP (api.census.gov pep)", "pep_county.csv", "src.fetch_pep", "fetch_pep_county"),
    ("FRED API", "building_permits.csv", "src.fetch_permits", "fetch_building_permits"),
    ("FBI CDE (data.gov)", "crime_state_proxy.csv", "src.fetch_crime", "fetch_crime_state"),
    ("FHFA HPI (fhfa.gov)", "fhfa_hpi.csv", "src.fetch_fhfa", "fetch_fhfa_hpi"),
    ("Zillow Research", "zillow_zhvi.csv", "src.fetch_zillow", "fetch_zillow_zhvi"),
    ("FHWA HPMS (geo.dot.gov)", "traffic_county.csv", "src.fetch_traffic", "fetch_traffic"),
    ("BTS NTAD (data.transportation.gov)", "ntad_traffic.csv", "src.fetch_ntad", "fetch_ntad_traffic"),
    ("BLM MLRS (gis.blm.gov)", "blm_leases.csv", "src.fetch_blm", "fetch_blm_leases"),
    ("Texas RRC (rrc.texas.gov)", "rrc_wells.csv", "src.fetch_rrc", "fetch_rrc_wells"),
]


def _has_live_rows(df: pd.DataFrame, raw_name: str) -> bool:
    if df.empty:
        return False
    if raw_name == "rrc_wells.csv" and "rrc_well_count" in df.columns:
        return df["rrc_well_count"].notna().any()
    if "note" in df.columns:
        notes = df["note"].fillna("").astype(str)
        if notes.str.contains("unavailable|sample|error|requires browser", case=False).all():
            return False
    numeric_cols = df.select_dtypes("number").columns
    if len(numeric_cols):
        return df[numeric_cols].notna().any().any()
    return True


def main() -> None:
    ensure_dirs()
    missing = missing_api_keys()
    if missing:
        print(f"WARNING: missing keys: {', '.join(missing)}")

    print(f"{'STATUS':<6} {'SOURCE':<42} {'ROWS':>4}  DETAIL")
    print("-" * 90)

    ok_count = 0
    for label, raw_name, module_name, fn_name in FETCHERS:
        import importlib

        module = importlib.import_module(module_name)
        fn = getattr(module, fn_name)
        try:
            df = fn()
            live = _has_live_rows(df, raw_name)
            status = "OK" if live else "PARTIAL"
            if live:
                ok_count += 1
            detail = ""
            if "note" in df.columns:
                detail = str(df["note"].dropna().iloc[0]) if df["note"].notna().any() else ""
            print(f"{status:<6} {label:<42} {len(df):>4}  {detail[:40]}")
            df.to_csv(RAW_DIR / raw_name, index=False)
        except Exception as exc:
            print(f"{'FAIL':<6} {label:<42} {'0':>4}  {exc}")

    print("-" * 90)
    print(f"Live sources: {ok_count}/{len(FETCHERS)}")
    print(f"Raw files in: {RAW_DIR}")


if __name__ == "__main__":
    main()
