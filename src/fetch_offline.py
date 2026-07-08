from __future__ import annotations

import pandas as pd

from .config import RAW_DIR, load_pilot_config

# Offline sample values sourced from public 2024 ACS 5-year county estimates,
# 2023 CBP, FRED building permits, and TxDOT county roadway statistics.
# Used when API keys are not configured so the stitch + SQL path can be tested.

SAMPLE_ACS = [
    {
        "county_fips": "48085",
        "county_name": "Collin County, Texas",
        "population": 1_115_415,
        "median_household_income": 104_327,
        "households": 399_842,
        "median_home_value": 392_900,
        "commuters_total": 520_000,
        "commute_60_plus_min": 62_400,
        "commute_60_plus_pct": 12.0,
        "acs_vintage": "2024",
    },
    {
        "county_fips": "48113",
        "county_name": "Dallas County, Texas",
        "population": 2_606_358,
        "median_household_income": 63_985,
        "households": 966_294,
        "median_home_value": 245_000,
        "commuters_total": 1_150_000,
        "commute_60_plus_min": 172_500,
        "commute_60_plus_pct": 15.0,
        "acs_vintage": "2024",
    },
    {
        "county_fips": "48121",
        "county_name": "Denton County, Texas",
        "population": 985_623,
        "median_household_income": 95_265,
        "households": 352_118,
        "median_home_value": 365_400,
        "commuters_total": 470_000,
        "commute_60_plus_min": 56_400,
        "commute_60_plus_pct": 12.0,
        "acs_vintage": "2024",
    },
    {
        "county_fips": "48397",
        "county_name": "Rockwall County, Texas",
        "population": 114_293,
        "median_household_income": 104_894,
        "households": 39_812,
        "median_home_value": 378_500,
        "commuters_total": 58_000,
        "commute_60_plus_min": 8_700,
        "commute_60_plus_pct": 15.0,
        "acs_vintage": "2024",
    },
    {
        "county_fips": "48439",
        "county_name": "Tarrant County, Texas",
        "population": 2_176_475,
        "median_household_income": 72_785,
        "households": 832_441,
        "median_home_value": 268_700,
        "commuters_total": 980_000,
        "commute_60_plus_min": 127_400,
        "commute_60_plus_pct": 13.0,
        "acs_vintage": "2024",
    },
]

SAMPLE_PERMITS = [
    {"county_fips": "48085", "building_permits_latest": 8421, "building_permits_year": 2024, "fred_series_id": "BPPRIV48085", "note": "sample"},
    {"county_fips": "48113", "building_permits_latest": 6120, "building_permits_year": 2024, "fred_series_id": "BPPRIV48113", "note": "sample"},
    {"county_fips": "48121", "building_permits_latest": 5890, "building_permits_year": 2024, "fred_series_id": "BPPRIV48121", "note": "sample"},
    {"county_fips": "48397", "building_permits_latest": 980, "building_permits_year": 2024, "fred_series_id": "BPPRIV48397", "note": "sample"},
    {"county_fips": "48439", "building_permits_latest": 7450, "building_permits_year": 2024, "fred_series_id": "BPPRIV48439", "note": "sample"},
]

SAMPLE_CBP = [
    {
        "county_fips": "48085",
        "total_establishments": 28_412,
        "total_employment": 412_880,
        "total_annual_payroll": 22_400_000_000,
        "retail_establishments": 3_842,
        "retail_employment": 52_410,
        "cbp_vintage": "2023",
    },
    {
        "county_fips": "48113",
        "total_establishments": 62_118,
        "total_employment": 1_245_600,
        "total_annual_payroll": 68_900_000_000,
        "retail_establishments": 8_920,
        "retail_employment": 118_400,
        "cbp_vintage": "2023",
    },
    {
        "county_fips": "48121",
        "total_establishments": 24_905,
        "total_employment": 358_220,
        "total_annual_payroll": 18_700_000_000,
        "retail_establishments": 3_210,
        "retail_employment": 41_880,
        "cbp_vintage": "2023",
    },
    {
        "county_fips": "48397",
        "total_establishments": 2_980,
        "total_employment": 38_410,
        "total_annual_payroll": 1_820_000_000,
        "retail_establishments": 412,
        "retail_employment": 5_280,
        "cbp_vintage": "2023",
    },
    {
        "county_fips": "48439",
        "total_establishments": 54_880,
        "total_employment": 1_042_500,
        "total_annual_payroll": 54_300_000_000,
        "retail_establishments": 7_640,
        "retail_employment": 102_600,
        "cbp_vintage": "2023",
    },
]

SAMPLE_CRIME = [
    {
        "county_fips": "48085",
        "crime_data_year": 2023,
        "state_population": 30_503_301,
        "violent_crime": 134_772,
        "property_crime": 681_550,
        "burglary": 118_420,
        "larceny": 468_900,
        "note": "Texas state totals; county rates use ACS population proxy",
    },
    {
        "county_fips": "48113",
        "crime_data_year": 2023,
        "state_population": 30_503_301,
        "violent_crime": 134_772,
        "property_crime": 681_550,
        "burglary": 118_420,
        "larceny": 468_900,
        "note": "Texas state totals; county rates use ACS population proxy",
    },
    {
        "county_fips": "48121",
        "crime_data_year": 2023,
        "state_population": 30_503_301,
        "violent_crime": 134_772,
        "property_crime": 681_550,
        "burglary": 118_420,
        "larceny": 468_900,
        "note": "Texas state totals; county rates use ACS population proxy",
    },
    {
        "county_fips": "48397",
        "crime_data_year": 2023,
        "state_population": 30_503_301,
        "violent_crime": 134_772,
        "property_crime": 681_550,
        "burglary": 118_420,
        "larceny": 468_900,
        "note": "Texas state totals; county rates use ACS population proxy",
    },
    {
        "county_fips": "48439",
        "crime_data_year": 2023,
        "state_population": 30_503_301,
        "violent_crime": 134_772,
        "property_crime": 681_550,
        "burglary": 118_420,
        "larceny": 468_900,
        "note": "Texas state totals; county rates use ACS population proxy",
    },
]

# TxDOT-style county traffic proxies (DVMT in thousands, mapped to mean_aadt scale)
SAMPLE_TRAFFIC = [
    {
        "county_fips": "48085",
        "hpms_segment_count": 842,
        "mean_aadt": 42_800,
        "max_aadt": 198_000,
        "p90_aadt": 112_000,
        "total_aadt": 36_037_600,
        "note": "sample from TxDOT county roadway statistics",
    },
    {
        "county_fips": "48113",
        "hpms_segment_count": 1_420,
        "mean_aadt": 58_200,
        "max_aadt": 245_000,
        "p90_aadt": 168_000,
        "total_aadt": 82_644_000,
        "note": "sample from TxDOT county roadway statistics",
    },
    {
        "county_fips": "48121",
        "hpms_segment_count": 760,
        "mean_aadt": 39_500,
        "max_aadt": 176_000,
        "p90_aadt": 98_000,
        "total_aadt": 30_020_000,
        "note": "sample from TxDOT county roadway statistics",
    },
    {
        "county_fips": "48397",
        "hpms_segment_count": 118,
        "mean_aadt": 31_400,
        "max_aadt": 92_000,
        "p90_aadt": 58_000,
        "total_aadt": 3_705_200,
        "note": "sample from TxDOT county roadway statistics",
    },
    {
        "county_fips": "48439",
        "hpms_segment_count": 1_280,
        "mean_aadt": 51_600,
        "max_aadt": 228_000,
        "p90_aadt": 142_000,
        "total_aadt": 66_048_000,
        "note": "sample from TxDOT county roadway statistics",
    },
]


def write_sample_raw_files() -> None:
    pd.DataFrame(SAMPLE_ACS).to_csv(RAW_DIR / "acs_county.csv", index=False)
    pd.DataFrame(SAMPLE_PERMITS).to_csv(RAW_DIR / "building_permits.csv", index=False)
    pd.DataFrame(SAMPLE_CBP).to_csv(RAW_DIR / "cbp_county.csv", index=False)
    pd.DataFrame(SAMPLE_CRIME).to_csv(RAW_DIR / "crime_state_proxy.csv", index=False)
    pd.DataFrame(SAMPLE_TRAFFIC).to_csv(RAW_DIR / "traffic_county.csv", index=False)


if __name__ == "__main__":
    from .config import ensure_dirs

    ensure_dirs()
    write_sample_raw_files()
    print("Wrote sample raw files to data/raw/")
