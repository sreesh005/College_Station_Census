"""Extract Reeves County doc-type catalog from GovOS preloaded HTML."""
import csv
import json
import re
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

html = requests.get("https://reeves.tx.publicsearch.us", timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
start = html.find('"docTypeMappings":')
if start < 0:
    raise SystemExit("docTypeMappings not found")
start += len('"docTypeMappings":')
depth = 0
end = start
for i, ch in enumerate(html[start:], start):
    if ch == "[":
        depth += 1
    elif ch == "]":
        depth -= 1
        if depth == 0:
            end = i + 1
            break

data = json.loads(html[start:end])
keywords = ("mineral", "oil", "gas", "lease", "royalty", "og", "petroleum", "deed", "assignment", "division", "pool")
rows = []
for group in data:
    gdesc = group.get("description", "")
    for dg in group.get("docGroup", []):
        for dt in dg.get("docType", []):
            desc = dt.get("description", "")
            code = dt.get("code", "")
            blob = f"{gdesc} {desc} {code}".lower()
            if any(k in blob for k in keywords):
                rows.append(
                    {
                        "category": gdesc,
                        "group": dg.get("description", ""),
                        "doc_type_code": code,
                        "doc_type_description": desc,
                    }
                )

path = OUT / "courthouse_reeves_mineral_doctypes.csv"
with path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["category", "group", "doc_type_code", "doc_type_description"])
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} rows to {path}")
