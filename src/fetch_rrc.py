from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, load_pilot_config

RRC_MFT_SHARE = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
RRC_HEADERS = {
    "User-Agent": "location-intelligence-pilot/1.0 (research; contact: local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _county_api_filename(county_fips: str) -> str:
    return f"api{county_fips[-3:]}.dbf"


def _parse_view_state(html: str) -> str | None:
    match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return match.group(1) if match else None


def _find_row_index(html: str, filename: str) -> int | None:
    pattern = rf'data-ri="(\d+)"[^>]*>.*?{re.escape(filename)}'
    match = re.search(pattern, html, re.S)
    return int(match.group(1)) if match else None


def _download_dbf(session: requests.Session, html: str, filename: str) -> bytes | None:
    row_idx = _find_row_index(html, filename)
    view_state = _parse_view_state(html)
    if row_idx is None or not view_state:
        return None

    data = {
        "fileList": "fileList",
        "javax.faces.ViewState": view_state,
        f"fileTable:{row_idx}:j_id_2f": f"fileTable:{row_idx}:j_id_2f",
    }
    response = session.post(RRC_MFT_SHARE, data=data, timeout=180)
    if response.status_code != 200:
        return None
    content_type = response.headers.get("content-type", "")
    if "dbf" in content_type or response.content[:1] == b"\x03":
        return response.content
    return None


def _read_dbf_row_count(content: bytes) -> int:
    try:
        from dbfread import DBF

        table = DBF(BytesIO(content))
        return len(list(table))
    except Exception:
        return max(0, int.from_bytes(content[4:8], "little", signed=False))


def fetch_rrc_wells() -> pd.DataFrame:
    """Texas RRC statewide API data — per-county DBF files from public MFT share."""
    cfg = load_pilot_config()
    session = requests.Session()
    session.headers.update(RRC_HEADERS)

    try:
        listing = session.get(RRC_MFT_SHARE, timeout=180)
        listing.raise_for_status()
        html = listing.text
    except requests.RequestException as exc:
        records = [
            {
                "county_fips": county["fips"],
                "rrc_well_count": pd.NA,
                "rrc_source_file": _county_api_filename(county["fips"]),
                "note": f"RRC MFT listing unavailable: {exc}",
            }
            for county in cfg["counties"]
        ]
        out = pd.DataFrame(records)
        out.to_csv(RAW_DIR / "rrc_wells.csv", index=False)
        return out

    records: list[dict] = []
    cache_dir = RAW_DIR / "rrc_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for county in cfg["counties"]:
        fips = county["fips"]
        filename = _county_api_filename(fips)
        cache_path = cache_dir / filename

        if filename not in html:
            records.append(
                {
                    "county_fips": fips,
                    "rrc_well_count": pd.NA,
                    "rrc_source_file": filename,
                    "note": "File not listed on RRC MFT share",
                }
            )
            continue

        content: bytes | None = None
        if cache_path.exists():
            content = cache_path.read_bytes()
        else:
            content = _download_dbf(session, html, filename)
            if content:
                cache_path.write_bytes(content)

        if not content:
            records.append(
                {
                    "county_fips": fips,
                    "rrc_well_count": pd.NA,
                    "rrc_source_file": filename,
                    "note": "Listed on MFT; programmatic download requires browser session",
                }
            )
            continue

        records.append(
            {
                "county_fips": fips,
                "rrc_well_count": _read_dbf_row_count(content),
                "rrc_source_file": filename,
                "note": "RRC statewide API DBF",
            }
        )

    out = pd.DataFrame(records)
    out["county_fips"] = out["county_fips"].astype(str).str.zfill(5)
    out.to_csv(RAW_DIR / "rrc_wells.csv", index=False)
    return out


if __name__ == "__main__":
    print(fetch_rrc_wells().to_string(index=False))
