"""Harvest samples without browser: RRC ArcGIS + GovOS HTMX search."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "location-intelligence-research/1.0"}


def rrc_gis_wells_midland(limit: int = 100) -> dict:
    """Query RRC public GIS well layer for Midland County (FIPS 329)."""
    # Discover layer
    folder = requests.get(
        "https://gis.rrc.texas.gov/server/rest/services/rrc_public?f=pjson",
        timeout=60,
    ).json()
    services = folder.get("services", [])
    if not services:
        return {"ok": False, "error": "no rrc_public services", "folder": folder}

    svc = services[0]["name"] + "/" + services[0]["type"]
    base = f"https://gis.rrc.texas.gov/server/rest/services/rrc_public/{svc}"
    meta = requests.get(base, params={"f": "pjson"}, timeout=60).json()
    layers = meta.get("layers", [])
    if not layers:
        return {"ok": False, "error": "no layers", "meta_keys": list(meta.keys())}

    layer_id = layers[0]["id"]
    query_url = f"{base}/{layer_id}/query"
    # Midland County RRC code often 329; also try county name
    for where in ["COUNTY='MIDLAND'", "COUNTY='329'", "API_County='329'", "1=1"]:
        r = requests.get(
            query_url,
            params={
                "where": where,
                "outFields": "*",
                "returnGeometry": "false",
                "resultRecordCount": limit,
                "f": "json",
            },
            timeout=90,
        )
        data = r.json()
        feats = data.get("features", [])
        if feats:
            rows = [f["attributes"] for f in feats]
            df = pd.DataFrame(rows)
            csv_path = OUT / "rrc_gis_midland_wells_sample.csv"
            df.to_csv(csv_path, index=False)
            return {
                "ok": True,
                "where": where,
                "rows": len(df),
                "columns": list(df.columns)[:20],
                "path": str(csv_path),
            }
    return {"ok": False, "error": "no features", "layer": layers[0]}


def govos_htmx_search(county: str, term: str, limit: int = 25) -> dict:
    """GovOS PublicSearch uses HTMX - probe search results endpoint."""
    base = f"https://{county}.tx.publicsearch.us"
    session = requests.Session()
    session.headers.update(
        {
            **HEADERS,
            "Accept": "text/html",
            "HX-Request": "true",
            "HX-Target": "search-results",
        }
    )
    session.get(base, timeout=30)

    attempts = []
    paths = [
        ("/search/results", {"department": "RP", "searchType": "quick", "searchQuery": term}),
        ("/search/results", {"department": "RP", "searchType": "advanced", "grantorGrantee": term}),
        ("/results", {"q": term, "dept": "RP"}),
    ]
    for path, params in paths:
        r = session.get(base + path, params=params, timeout=30)
        # Parse result rows from HTML
        doc_rows = re.findall(
            r'data-testid="document-row"[^>]*>(.*?)</tr>|class="[^"]*result[^"]*"[^>]*>(.*?)</tr>',
            r.text,
            re.S | re.I,
        )
        instrument = re.findall(r"(MINERAL|OIL|GAS|LEASE|ROYALTY|DEED)[^<]{0,40}", r.text, re.I)
        doc_nums = re.findall(r"doc(?:ument)?\s*#?\s*:?\s*(\d{6,})", r.text, re.I)
        attempts.append(
            {
                "path": path,
                "params": params,
                "status": r.status_code,
                "html_len": len(r.text),
                "doc_rows": len(doc_rows),
                "instrument_hits": instrument[:10],
                "doc_nums": doc_nums[:10],
            }
        )
        if doc_nums or len(instrument) > 3:
            snippet = re.sub(r"\s+", " ", r.text[:8000])
            (OUT / f"govos_{county}_{term.replace(' ', '_')}_snippet.html").write_text(
                r.text[:50000], encoding="utf-8"
            )
            # Extract structured table data if present
            cells = re.findall(r"<td[^>]*>([^<]{1,120})</td>", r.text)
            if cells:
                rows = [cells[i : i + 6] for i in range(0, min(len(cells), 120), 6)]
                pd.DataFrame(rows).to_csv(
                    OUT / f"courthouse_{county}_mineral_index_sample.csv",
                    index=False,
                    header=False,
                )
                return {"ok": True, "county": county, "term": term, "cells": len(cells), "attempt": attempts[-1]}

    return {"ok": False, "county": county, "term": term, "attempts": attempts}


def main() -> None:
    summary = {
        "rrc_gis": rrc_gis_wells_midland(100),
        "midland_mineral": govos_htmx_search("midland", "mineral deed"),
        "midland_lease": govos_htmx_search("midland", "oil gas lease"),
        "reeves_royalty": govos_htmx_search("reeves", "royalty deed"),
        "tarrant_mineral": govos_htmx_search("tarrant", "mineral deed"),
    }
    (OUT / "harvest_no_browser_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
