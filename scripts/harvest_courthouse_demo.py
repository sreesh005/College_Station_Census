"""Harvest courthouse mineral index rows via GovOS browser (demo)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

SEARCHES = [
    ("reeves", "mineral deed"),
    ("reeves", "oil gas lease"),
    ("midland", "mineral deed"),
]
MAX_PER_SEARCH = 50


def parse_table_text(text: str) -> list[dict]:
    rows: list[dict] = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.upper().startswith("GRANTOR") or "Search results table" in ln:
            continue
        parts = [p.strip() for p in re.split(r"\t+", ln) if p.strip()]
        if len(parts) >= 7:
            rows.append(
                {
                    "grantor": parts[0],
                    "grantee": parts[1],
                    "doc_type": parts[2],
                    "recorded_date": parts[3],
                    "doc_number": parts[4],
                    "book_volume_page": parts[5],
                    "legal_description": parts[6],
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
        page.wait_for_timeout(7000)
        if page.locator("table").count() == 0:
            page.goto(f"https://{county}.tx.publicsearch.us", wait_until="domcontentloaded", timeout=90000)
            page.locator("#basicSearchInputBox").fill(query)
            page.locator("button:has-text('Search')").first.click()
            page.wait_for_url(re.compile(r"/results"), timeout=60000)
            page.wait_for_timeout(5000)
        table_text = page.locator("table").first.inner_text()
        browser.close()
    rows = parse_table_text(table_text)[:MAX_PER_SEARCH]
    for r in rows:
        r["county"] = county
        r["search_query"] = query
        r["source_url"] = url
    return rows


def main() -> None:
    all_rows: list[dict] = []
    for county, query in SEARCHES:
        rows = harvest(county, query)
        print(f"{county} / '{query}': {len(rows)} rows")
        all_rows.extend(rows)

    fields = [
        "county", "search_query", "grantor", "grantee", "doc_type",
        "recorded_date", "doc_number", "book_volume_page", "legal_description", "source_url",
    ]
    csv_path = OUT / "courthouse_mineral_index_harvest.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    mineral = [
        r for r in all_rows
        if re.search(r"mineral|lease|royalt|conveyance|og|oil|gas", r.get("doc_type", ""), re.I)
    ]
    mineral_path = OUT / "courthouse_mineral_only_sample.csv"
    with mineral_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(mineral)

    summary = {
        "ok": len(all_rows) > 0,
        "total_rows": len(all_rows),
        "mineral_related_rows": len(mineral),
        "csv": str(csv_path),
        "mineral_csv": str(mineral_path),
        "sample": all_rows[:5],
    }
    (OUT / "courthouse_harvest_demo.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
