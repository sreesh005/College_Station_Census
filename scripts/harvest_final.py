"""Pull RRC GIS well sample + probe GovOS with retries."""
import json
from pathlib import Path

import pandas as pd
import requests

OUT = Path("data/samples")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer/1"


def rrc_gis_sample() -> dict:
    fields = requests.get(BASE, params={"f": "pjson"}, timeout=60).json()
    field_names = [f["name"] for f in fields.get("fields", [])]
    # Midland County bounding box (approx)
    geometry = {
        "xmin": -102.25,
        "ymin": 31.75,
        "xmax": -101.85,
        "ymax": 32.05,
        "spatialReference": {"wkid": 4326},
    }
    r = requests.get(
        BASE + "/query",
        params={
            "geometry": json.dumps(geometry),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": 200,
            "f": "json",
        },
        timeout=120,
    )
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return {"ok": False, "error": data.get("error", "no features"), "fields": field_names[:15]}
    rows = [f["attributes"] for f in feats]
    df = pd.DataFrame(rows)
    path = OUT / "rrc_gis_midland_wells_sample.csv"
    df.to_csv(path, index=False)
    return {"ok": True, "rows": len(df), "columns": list(df.columns), "path": str(path)}


def govos_quick(county: str, term: str) -> dict:
    base = f"https://{county}.tx.publicsearch.us"
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    try:
        session.get(base, timeout=60)
        r = session.get(
            f"{base}/search/results",
            params={"department": "RP", "searchType": "quick", "searchQuery": term},
            timeout=90,
        )
    except Exception as exc:
        return {"ok": False, "county": county, "error": str(exc)}
    import re

    cells = re.findall(r"<td[^>]*>([^<]{1,200})</td>", r.text)
    ok = len(cells) > 10
    result = {"ok": ok, "county": county, "term": term, "status": r.status_code, "cells": len(cells)}
    if ok:
        rows = [cells[i : i + 7] for i in range(0, min(len(cells), 140), 7)]
        path = OUT / f"courthouse_{county}_index_sample.csv"
        pd.DataFrame(rows).to_csv(path, index=False, header=False)
        result["path"] = str(path)
        result["preview"] = cells[:14]
    else:
        result["html_len"] = len(r.text)
    return result


def main() -> None:
    summary = {
        "rrc_gis": rrc_gis_sample(),
        "reeves": govos_quick("reeves", "mineral deed"),
        "tarrant": govos_quick("tarrant", "mineral deed"),
    }
    (OUT / "harvest_final_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
