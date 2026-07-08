from __future__ import annotations

import pandas as pd

from .config import EXPORTS_DIR, ensure_dirs

DASHBOARD_COLUMNS = [
    "county_label",
    "county_role",
    "county_fips",
    "population",
    "pep_population",
    "median_household_income",
    "households",
    "median_home_value",
    "fhfa_hpi_index_nsa",
    "zillow_zhvi",
    "building_permits_latest",
    "building_permits_year",
    "permits_per_1k_households",
    "total_establishments",
    "total_employment",
    "total_annual_payroll",
    "retail_establishments",
    "retail_employment",
    "retail_establishments_per_10k_pop",
    "mean_aadt",
    "max_aadt",
    "p90_aadt",
    "ntad_system_miles",
    "rrc_well_count",
    "blm_lease_count",
    "blm_lease_acres",
    "violent_crime_per_100k",
    "property_crime_per_100k",
    "burglary_per_100k",
    "larceny_per_100k",
    "general_location_score",
    "score_population",
    "score_income",
    "score_growth",
    "score_traffic",
    "score_retail_density",
    "score_crime",
]


def export_dashboard_csv(county_features: pd.DataFrame) -> pd.DataFrame:
    ensure_dirs()
    available = [col for col in DASHBOARD_COLUMNS if col in county_features.columns]
    dashboard = county_features[available].copy()
    dashboard = dashboard.sort_values("general_location_score", ascending=False)
    dashboard.to_csv(EXPORTS_DIR / "county_dashboard.csv", index=False)
    county_features.to_csv(EXPORTS_DIR / "county_features_full.csv", index=False)
    return dashboard
