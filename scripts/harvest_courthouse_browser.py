"""Demonstrate courthouse mineral index harvest via GovOS browser search."""
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


def harvest_county(page, county: str, query: str, api_log: list) -> list[dict]:
    base = f"https://{county}.tx.publicsearch.us"
    captured: list[dict] = []

    def on_response(resp):
        url = resp.url
        if any(k in url for k in ("search", "document", "ko-search", "graphql", "elastic", "api")):
            try:
                body = resp.text() if "json" in (resp.headers.get("content-type") or "") else ""
            except Exception:
                body = ""
            api_log.append({"url": url, "status": resp.status, "body_preview": body[:500]})

    page.on("response", on_response)
    page.goto(base, wait_until="networkidle", timeout=90000)

    # Quick search form
    page.get_by_label("Search Term", exact=False).fill(query)
    page.get_by_role("button", name=re.compile("Search", re.I)).first.click()
    page.wait_for_timeout(5000)

    # Results table rows
    rows = page.locator("table tbody tr")
    count = rows.count()
    for i in range(min(count, 50)):
        cells = rows.nth(i).locator("td")
        if cells.count() < 4:
            continue
        texts = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
        if not any(texts):
            continue
        captured.append(
            {
                "county": county,
                "search_query": query,
                "grantor": texts[0] if len(texts) > 0 else "",
                "grantee": texts[1] if len(texts) > 1 else "",
                "doc_type": texts[2] if len(texts) > 2 else "",
                "recorded_date": texts[3] if len(texts) > 3 else "",
                "instrument": texts[4] if len(texts) > 4 else "",
                "raw_cells": " | ".join(texts),
            }
        )

    # Fallback: parse visible result cards if table layout differs
    if not captured:
        items = page.locator('[data-testid*="result"], [class*="result-row"], [class*="ResultRow"]')
        for i in range(min(items.count(), 50)):
            text = items.nth(i).inner_text().strip()
            if len(text) > 20:
                captured.append(
                    {
                        "county": county,
                        "search_query": query,
                        "grantor": "",
                        "grantee": "",
                        "doc_type": "",
                        "recorded_date": "",
                        "instrument": "",
                        "raw_cells": re.sub(r"\s+", " ", text)[:500],
                    }
                )

    return captured


def main() -> None:
    all_rows: list[dict] = []
    api_log: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for county, query in SEARCHES:
            try:
                rows = harvest_county(page, county, query, api_log)
                all_rows.extend(rows)
                print(f"{county} / {query}: {len(rows)} rows")
            except Exception as exc:
                print(f"{county} / {query}: ERROR {exc}")
                page.screenshot(path=str(OUT / f"harvest_error_{county}.png"))
        browser.close()

    # Dedupe by raw_cells
    seen = set()
    unique = []
    for r in all_rows:
        key = r.get("raw_cells", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    csv_path = OUT / "courthouse_mineral_index_harvest.csv"
    fields = ["county", "search_query", "grantor", "grantee", "doc_type", "recorded_date", "instrument", "raw_cells"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(unique)

    summary = {
        "total_rows": len(unique),
        "by_search": {f"{r['county']}|{r['search_query']}": sum(1 for x in unique if x["county"] == r["county"] and x["search_query"] == r["search_query"]) for r in unique},
        "csv": str(csv_path),
        "api_calls_captured": len(api_log),
        "api_samples": api_log[:15],
    }
    (OUT / "courthouse_harvest_demo.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
