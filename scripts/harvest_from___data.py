"""Extract courthouse rows from GovOS window.__data JSON embedded in results page."""
import json
import re
import csv
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("data/samples")
COUNTY = "reeves"
QUERY = "mineral deed"
URL = f"https://{COUNTY}.tx.publicsearch.us/results?department=RP&searchType=quickSearch&searchQuery=mineral+deed"


def extract_documents(html: str) -> list[dict]:
    m = re.search(r"window\.__data=(\{.*?\});</script>", html, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    # Walk tree for document-like dicts
    docs: list[dict] = []

    def walk(obj):
        if isinstance(obj, dict):
            if "grantors" in obj or "grantor" in obj or "docType" in obj or "documentNumber" in obj:
                docs.append(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return docs


def normalize(doc: dict) -> dict:
    grantors = doc.get("grantors") or doc.get("grantor") or []
    grantees = doc.get("grantees") or doc.get("grantee") or []
    if isinstance(grantors, list):
        grantor = "; ".join(
            g.get("name", str(g)) if isinstance(g, dict) else str(g) for g in grantors
        )
    else:
        grantor = str(grantors)
    if isinstance(grantees, list):
        grantee = "; ".join(
            g.get("name", str(g)) if isinstance(g, dict) else str(g) for g in grantees
        )
    else:
        grantee = str(grantees)
    legals = doc.get("legals") or doc.get("legalDescription") or ""
    if isinstance(legals, list):
        legal = "; ".join(str(x) for x in legals)
    else:
        legal = str(legals)
    return {
        "grantor": grantor,
        "grantee": grantee,
        "doc_type": doc.get("docType") or doc.get("docTypeDescription") or doc.get("instrumentType") or "",
        "recorded_date": doc.get("recordedDate") or doc.get("recordDate") or "",
        "doc_number": str(doc.get("documentNumber") or doc.get("docNumber") or doc.get("instrumentNumber") or ""),
        "legal_description": legal,
    }


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(5000)
        html = page.content()
        browser.close()

    raw_docs = extract_documents(html)
    rows = [normalize(d) for d in raw_docs]
    # dedupe
    seen = set()
    unique = []
    for r in rows:
        key = r.get("doc_number") or r.get("grantor", "") + r.get("grantee", "")
        if key and key not in seen:
            seen.add(key)
            r["county"] = COUNTY
            r["search_query"] = QUERY
            unique.append(r)

    path = OUT / "courthouse_mineral_index_harvest.csv"
    fields = ["county", "search_query", "grantor", "grantee", "doc_type", "recorded_date", "doc_number", "legal_description"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(unique[:50])

    print("raw_docs", len(raw_docs), "unique", len(unique))
    print(json.dumps(unique[:3], indent=2))


if __name__ == "__main__":
    main()
