"""Harvest courthouse index by parsing rendered table text."""
import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("data/samples")
SEARCHES = [
    ("reeves", "mineral deed"),
    ("reeves", "oil gas lease"),
    ("midland", "mineral deed"),
]


def parse_table_text(text: str) -> list[dict]:
    rows = []
    # Lines with tab-separated or multi-space columns after header
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if ln.upper().startswith("GRANTOR") or ln.startswith("Search results"):
            continue
        # Match pattern: GRANTOR GRANTEE DOC_TYPE DATE DOCNUM ...
        m = re.match(
            r"^([A-Z0-9][A-Z0-9 .,'&/-]{2,60}?)\s+([A-Z0-9][A-Z0-9 .,'&/-]{2,60}?)\s+"
            r"(MINERAL[^0-9]{3,40}|MEMORANDUM[^0-9]{3,40}|OIL[^0-9]{3,40}|GAS[^0-9]{3,40}|"
            r"ROYALTY[^0-9]{3,40}|ASSIGNMENT[^0-9]{3,40}|LEASE[^0-9]{3,40}|DEED[^0-9]{3,40}|"
            r"RIGHT OF WAY|EASEMENT|AFFIDAVIT|TERMINATION|APPLICATION|LIEN[^0-9]{3,40}|"
            r"UNIT [A-Z/ ]{3,40}|[A-Z][A-Z /-]{4,40})\s+"
            r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{6,})\s+"
            r"(--/--/--|\d+/\d+/\d+)\s+(.+)$",
            ln,
        )
        if m:
            rows.append(
                {
                    "grantor": m.group(1).strip(),
                    "grantee": m.group(2).strip(),
                    "doc_type": m.group(3).strip(),
                    "recorded_date": m.group(4).strip(),
                    "doc_number": m.group(5).strip(),
                    "book_volume_page": m.group(6).strip(),
                    "legal_description": m.group(7).strip(),
                }
            )
    return rows


def harvest(county: str, query: str) -> list[dict]:
    q = query.replace(" ", "+")
    url = f"https://{county}.tx.publicsearch.us/results?department=RP&searchType=quickSearch&searchQuery={q}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(6000)
        table_text = page.locator("table").first.inner_text()
        browser.close()
    rows = parse_table_text(table_text)
    for r in rows:
        r["county"] = county
        r["search_query"] = query
        r["source_url"] = url
    return rows


def main():
    all_rows = []
    for county, query in SEARCHES:
        rows = harvest(county, query)
        print(f"{county} / {query}: {len(rows)} rows")
        all_rows.extend(rows[:40])

    fields = [
        "county", "search_query", "grantor", "grantee", "doc_type",
        "recorded_date", "doc_number", "book_volume_page", "legal_description", "source_url",
    ]
    path = OUT / "courthouse_mineral_index_harvest.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    mineral = [r for r in all_rows if re.search(r"mineral|lease|royalt|conveyance", r["doc_type"], re.I)]
    summary = {"ok": len(all_rows) > 0, "total": len(all_rows), "mineral_related": len(mineral), "sample": all_rows[:5]}
    (OUT / "courthouse_harvest_demo.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
