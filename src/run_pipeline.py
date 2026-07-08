from __future__ import annotations

import argparse
import traceback

from .config import ROOT, ensure_dirs, missing_api_keys
from .fetch_acs import fetch_acs_county
from .fetch_blm import fetch_blm_leases
from .fetch_cbp import fetch_cbp
from .fetch_crime import fetch_crime_state
from .fetch_fhfa import fetch_fhfa_hpi
from .fetch_ntad import fetch_ntad_traffic
from .fetch_offline import write_sample_raw_files
from .fetch_pep import fetch_pep_county
from .fetch_permits import fetch_building_permits
from .fetch_rrc import fetch_rrc_wells
from .fetch_traffic import fetch_traffic
from .fetch_zillow import fetch_zillow_zhvi
from .load_sqlite import load_sqlite
from .stitch import stitch_county_features


def run(skip_traffic: bool = False, offline: bool = False) -> None:
    ensure_dirs()
    missing = missing_api_keys()

    if offline or missing:
        if not offline:
            env_path = ROOT / ".env"
            if env_path.exists() and env_path.stat().st_size == 0:
                print(f"{env_path} exists but is empty — save your keys in the editor, then re-run.")
            elif missing:
                print(f"Missing or invalid keys in .env: {', '.join(missing)}")
            print("Using bundled sample public data for this run.\n")
            print("Expected format (no quotes):")
            print("CENSUS_API_KEY=...")
            print("FRED_API_KEY=...")
            print("DATA_GOV_API_KEY=...\n")
        write_sample_raw_files()
    else:
        steps: list[tuple[str, callable]] = [
            ("ACS demographics (api.census.gov acs/acs5)", fetch_acs_county),
            ("Census PEP (api.census.gov pep)", fetch_pep_county),
            ("Building permits (FRED)", fetch_building_permits),
            ("County Business Patterns (Census CBP)", fetch_cbp),
            ("Crime (FBI CDE / data.gov)", fetch_crime_state),
            ("FHFA HPI (fhfa.gov CSV)", fetch_fhfa_hpi),
            ("Zillow ZHVI (zillow.com/research)", fetch_zillow_zhvi),
            ("BLM MLRS leases (gis.blm.gov)", fetch_blm_leases),
            ("Texas RRC wells (rrc.texas.gov MFT)", fetch_rrc_wells),
        ]
        if not skip_traffic:
            steps.extend(
                [
                    ("FHWA HPMS traffic (geo.dot.gov)", fetch_traffic),
                    ("BTS NTAD county summary (data.transportation.gov)", fetch_ntad_traffic),
                ]
            )

        for label, fn in steps:
            print(f"\n==> {label}")
            try:
                result = fn()
                print(result.head().to_string(index=False))
            except Exception as exc:
                print(f"FAILED: {exc}")
                traceback.print_exc()

    print("\n==> Stitch county features")
    stitched = stitch_county_features()
    print(stitched[["county_label", "general_location_score"]].to_string(index=False))

    print("\n==> Load SQLite for Power BI")
    load_sqlite()
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Location intelligence pilot pipeline")
    parser.add_argument("--skip-traffic", action="store_true", help="Skip HPMS / NTAD traffic sources")
    parser.add_argument("--offline", action="store_true", help="Use bundled sample data only")
    args = parser.parse_args()
    run(skip_traffic=args.skip_traffic, offline=args.offline)


if __name__ == "__main__":
    main()
