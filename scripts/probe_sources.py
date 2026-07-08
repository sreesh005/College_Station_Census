"""Quick probe of all external data sources."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

CENSUS = os.getenv("CENSUS_API_KEY", "").strip()
FRED = os.getenv("FRED_API_KEY", "").strip()
DG = os.getenv("DATA_GOV_API_KEY", "").strip()


def probe(name: str, fn) -> None:
    try:
        ok, detail = fn()
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")


def main() -> None:
    probe("Census ACS (acs/acs5)", lambda: (
        requests.get(
            "https://api.census.gov/data/2024/acs/acs5",
            params={"get": "NAME,B01001_001E", "for": "county:113", "in": "state:48", "key": CENSUS},
            timeout=60,
        ).json()[1][1] != "",
        "Dallas population via ACS",
    ))

    probe("Census PEP (pep)", lambda: (
        (r := requests.get(
            "https://api.census.gov/data/2023/pep/charv",
            params={"get": "POP", "for": "county:113", "in": "state:48", "YEAR": 2023, "key": CENSUS},
            timeout=60,
        )).status_code == 200,
        r.json()[1][0] if r.ok else r.text[:80],
    ))

    probe("FRED API", lambda: (
        requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": "BPPRIV048113", "api_key": FRED, "file_type": "json", "limit": 1},
            timeout=60,
        ).status_code == 200,
        "Dallas permits series",
    ))

    probe("FBI CDE (cde.ucr.cjis.gov via data.gov)", lambda: (
        (r := requests.get(
            "https://api.usa.gov/crime/fbi/cde/summarized/state/TX/violent-crime",
            params={"api_key": DG, "from": "01-2023", "to": "12-2023"},
            timeout=60,
        )).status_code == 200,
        str(r.json())[:120] if r.ok else r.text[:120],
    ))

    probe("FHFA HPI (fhfa.gov)", lambda: (
        (r := requests.get(
            "https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv",
            timeout=120,
            stream=True,
        )).status_code == 200,
        f"header: {next(r.iter_lines()).decode()[:80]}" if r.ok else r.text[:80],
    ))

    probe("Zillow Research ZHVI", lambda: (
        (r := requests.get(
            "https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
            timeout=120,
            stream=True,
        )).status_code == 200,
        f"header: {next(r.iter_lines()).decode()[:80]}" if r.ok else r.text[:80],
    ))

    probe("FHWA HPMS (geo.dot.gov ArcGIS)", lambda: (
        (r := requests.get(
            "https://geo.dot.gov/server/rest/services/Hosted/Texas_2018_PR/FeatureServer/0/query",
            params={
                "where": "county_code=113 AND aadt>0",
                "outFields": "route_id,aadt,county_code",
                "resultRecordCount": 3,
                "f": "json",
            },
            timeout=90,
        )).status_code == 200 and len(r.json().get("features", [])) > 0,
        f"features={len(r.json().get('features', []))}" if r.ok else r.text[:80],
    ))

    probe("BTS NTAD (data.transportation.gov)", lambda: (
        (r := requests.get(
            "https://data.transportation.gov/resource/8j5p-a5aj.json",
            params={"$limit": "3", "$where": "stateid='48' AND countyid='113'"},
            timeout=180,
        )).status_code == 200 and len(r.json()) > 0,
        str(r.json()[:1])[:120] if r.ok else r.text[:120],
    ))

    probe("BLM MLRS (gis.blm.gov)", lambda: (
        (r := requests.get(
            "https://gis.blm.gov/nlsdb/rest/services/HUB/BLM_Natl_MLRS_Oil_and_Gas_Leases/FeatureServer/0/query",
            params={
                "where": "GEO_STATE='TX'",
                "geometry": json.dumps(
                    {"xmin": -97.05, "ymin": 32.55, "xmax": -96.45, "ymax": 33.05, "spatialReference": {"wkid": 4326}}
                ),
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "returnCountOnly": "true",
                "f": "json",
            },
            timeout=90,
        )).status_code == 200 and r.json().get("count", 0) >= 0,
        f"tx_lease_count={r.json().get('count')}" if r.ok else r.text[:120],
    ))

    probe("Texas RRC (rrc.texas.gov MFT)", lambda: (
        (r := requests.get(
            "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
            timeout=120,
        )).status_code == 200 and "api113.dbf" in r.text,
        "statewide API DBF folder lists api113.dbf" if r.ok and "api113.dbf" in r.text else r.text[:80],
    ))


if __name__ == "__main__":
    main()
