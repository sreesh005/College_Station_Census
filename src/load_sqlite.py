from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import create_engine, text

from .config import PROCESSED_DIR, RAW_DIR, SQLITE_PATH, EXPORTS_DIR, ensure_dirs, load_pilot_config
from .export_csv import export_dashboard_csv
from .stitch import stitch_county_features


def load_sqlite() -> None:
    ensure_dirs()
    cfg = load_pilot_config()
    county_features = stitch_county_features()
    export_dashboard_csv(county_features)

    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()

    engine = create_engine(f"sqlite:///{SQLITE_PATH.as_posix()}")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE dim_pilot (
                    pilot_name TEXT,
                    state_fips TEXT,
                    state_abbr TEXT,
                    description TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO dim_pilot VALUES (:pilot_name, :state_fips, :state_abbr, :description)
                """
            ),
            {
                "pilot_name": cfg["pilot_name"],
                "state_fips": cfg["state_fips"],
                "state_abbr": cfg["state_abbr"],
                "description": cfg["pilot_description"],
            },
        )

        conn.execute(
            text(
                """
                CREATE TABLE dim_county (
                    county_fips TEXT PRIMARY KEY,
                    county_label TEXT,
                    county_role TEXT,
                    state_fips TEXT,
                    state_abbr TEXT
                )
                """
            )
        )
        counties = pd.DataFrame(cfg["counties"]).rename(
            columns={"fips": "county_fips", "name": "county_label", "role": "county_role"}
        )
        counties["state_fips"] = cfg["state_fips"]
        counties["state_abbr"] = cfg["state_abbr"]
        counties.to_sql("dim_county", conn, if_exists="append", index=False)

        county_features.to_sql("fact_county_features", conn, if_exists="replace", index=False)

        for raw_name in (
            "acs_county.csv",
            "pep_county.csv",
            "building_permits.csv",
            "cbp_county.csv",
            "crime_state_proxy.csv",
            "fhfa_hpi.csv",
            "zillow_zhvi.csv",
            "traffic_county.csv",
            "ntad_traffic.csv",
            "blm_leases.csv",
            "rrc_wells.csv",
        ):
            path = RAW_DIR / raw_name
            if not path.exists():
                continue
            table = raw_name.replace(".csv", "")
            pd.read_csv(path).to_sql(f"raw_{table}", conn, if_exists="replace", index=False)

        conn.execute(
            text(
                """
                CREATE VIEW vw_county_dashboard AS
                SELECT
                    d.county_label,
                    d.county_role,
                    f.county_fips,
                    f.population,
                    f.median_household_income,
                    f.households,
                    f.median_home_value,
                    f.building_permits_latest,
                    f.building_permits_year,
                    f.permits_per_1k_households,
                    f.total_establishments,
                    f.retail_establishments,
                    f.retail_employment,
                    f.retail_establishments_per_10k_pop,
                    f.mean_aadt,
                    f.max_aadt,
                    f.p90_aadt,
                    f.violent_crime_per_100k,
                    f.property_crime_per_100k,
                    f.general_location_score,
                    f.score_population,
                    f.score_income,
                    f.score_growth,
                    f.score_traffic,
                    f.score_retail_density,
                    f.score_crime
                FROM fact_county_features f
                JOIN dim_county d ON f.county_fips = d.county_fips
                ORDER BY f.general_location_score DESC
                """
            )
        )

    manifest = {
        "sqlite_path": str(SQLITE_PATH),
        "power_bi_connection": f"SQLite database file: {SQLITE_PATH}",
        "csv_exports": {
            "dashboard": str((EXPORTS_DIR / "county_dashboard.csv").resolve()),
            "full_features": str((EXPORTS_DIR / "county_features_full.csv").resolve()),
        },
        "recommended_tables": ["vw_county_dashboard", "fact_county_features", "dim_county"],
    }
    with open(PROCESSED_DIR / "power_bi_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    load_sqlite()
    print(f"Loaded SQLite database at {SQLITE_PATH}")
