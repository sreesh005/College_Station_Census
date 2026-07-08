"""Download small RRC file via MFT PrimeFaces session + harvest GovOS search sample."""
from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) location-intelligence-research/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def mft_download_file(share_url: str, filename: str, dest: Path) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)
    listing = session.get(share_url, timeout=120)
    listing.raise_for_status()
    html = listing.text
    if filename not in html:
        return {"ok": False, "error": f"{filename} not in listing"}

    view_state = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    row = re.search(rf'data-ri="(\d+)"[^>]*>.*?{re.escape(filename)}', html, re.S)
    if not view_state or not row:
        return {"ok": False, "error": "Could not parse ViewState or row index"}

    data = {
        "fileList": "fileList",
        "javax.faces.ViewState": view_state.group(1),
        f"fileTable:{row.group(1)}:j_id_2f": f"fileTable:{row.group(1)}:j_id_2f",
    }
    resp = session.post(share_url, data=data, timeout=180)
    if resp.status_code != 200:
        return {"ok": False, "error": f"POST status {resp.status_code}"}
    if len(resp.content) < 100:
        return {"ok": False, "error": "empty response"}
    dest.write_bytes(resp.content)
    return {"ok": True, "bytes": len(resp.content), "path": str(dest)}


def govos_search(county: str, query: str, limit: int = 25) -> dict:
    """GovOS Cloud Search uses ko-search backend - probe tenant API."""
    base = f"https://{county}.tx.publicsearch.us"
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "application/json, text/plain, */*"})
    home = session.get(base, timeout=30)
    tenant = county
    # Common GovOS/Kofile search API pattern used by many counties
    api_urls = [
        f"https://{county}.tx.publicsearch.us/api/search",
        f"https://search.govos.com/{county}.tx/publicsearch/search",
        f"https://api.govos.com/search/v1/{county}.tx",
    ]
    payload = {"query": query, "page": 1, "size": limit}
    for url in api_urls:
        try:
            r = session.post(url, json=payload, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                return {"ok": True, "url": url, "count": len(r.json().get("results", r.json()))}
        except Exception:
            pass

    # Fallback: parse HTML search results page if SSR exists
    r = session.get(
        f"{base}/search/results",
        params={"department": "RP", "searchType": "quick", "searchQuery": query},
        timeout=30,
    )
    rows = re.findall(r'data-testid="search-result-row"[^>]*>(.*?)</tr>', r.text, re.S)
    if not rows:
        # Try to find JSON embedded in page
        embedded = re.findall(r"__NEXT_DATA__\" type=\"application/json\">(.*?)</script>", r.text)
        if embedded:
            data = json.loads(embedded[0])
            return {"ok": True, "method": "next_data", "keys": list(data.keys())[:10]}
    return {"ok": False, "home_status": home.status_code, "results_status": r.status_code, "html_len": len(r.text)}


def read_dbf_sample(path: Path, n: int = 50) -> pd.DataFrame:
    from dbfread import DBF

    table = DBF(str(path), encoding="latin-1")
    return pd.DataFrame(list(table)[:n])


def main() -> None:
    summary: dict = {}

    # RRC - small county API DBF (Midland county = api165)
    rrc_result = mft_download_file(
        "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
        "api165.dbf",
        OUT / "rrc_api165_midland.dbf",
    )
    summary["rrc_midland_dbf"] = rrc_result
    if rrc_result.get("ok"):
        df = read_dbf_sample(OUT / "rrc_api165_midland.dbf", 100)
        csv_path = OUT / "rrc_midland_wells_sample.csv"
        df.to_csv(csv_path, index=False)
        summary["rrc_midland_rows"] = len(df)
        summary["rrc_midland_columns"] = list(df.columns)

    # RRC - tiny drilling permit pending file
    permit_result = mft_download_file(
        "https://mft.rrc.texas.gov/link/0ad92a65-4212-49a1-98a7-d667a55fb497",
        "dp_drilling_permit_pending_20210102170803.txt",
        OUT / "rrc_drilling_permit_sample.txt",
    )
    summary["rrc_permit_sample"] = permit_result
    if permit_result.get("ok"):
        text = (OUT / "rrc_drilling_permit_sample.txt").read_text(errors="replace")
        (OUT / "rrc_drilling_permit_sample_preview.txt").write_text(text[:5000], encoding="utf-8")

    # Courthouse GovOS - mineral-related searches
    for county, query in [
        ("midland", "mineral deed"),
        ("midland", "oil gas lease"),
        ("tarrant", "mineral deed"),
        ("reeves", "royalty deed"),
    ]:
        summary[f"govos_{county}_{query.replace(' ', '_')}"] = govos_search(county, query)

    out = OUT / "harvest_sample_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
