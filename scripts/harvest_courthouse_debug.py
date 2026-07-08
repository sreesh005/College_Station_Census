"""Debug GovOS browser search - capture API + page state."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("data/samples")
OUT.mkdir(parents=True, exist_ok=True)
COUNTY = "reeves"
QUERY = "mineral deed"
BASE = f"https://{COUNTY}.tx.publicsearch.us"

api_hits = []


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" in ct or "graphql" in resp.url or "document" in resp.url.lower():
                try:
                    body = resp.text()
                except Exception:
                    body = ""
                if body and len(body) > 50:
                    api_hits.append({"url": resp.url, "status": resp.status, "len": len(body), "body": body[:3000]})

        page.on("response", on_response)
        page.goto(BASE, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2000)

        # Try input selectors
        inputs = page.locator("input[type='text'], input:not([type])")
        print("inputs", inputs.count())
        for i in range(min(inputs.count(), 8)):
            el = inputs.nth(i)
            print(" input", i, el.get_attribute("name"), el.get_attribute("id"), el.get_attribute("placeholder"))

        # Fill search - try multiple strategies
        filled = False
        for sel in [
            "input[placeholder*='Search' i]",
            "input[name*='search' i]",
            "label:has-text('Search Term') + input",
            "input[type='text']",
        ]:
            loc = page.locator(sel)
            if loc.count():
                loc.first.fill(QUERY)
                filled = True
                print("filled via", sel)
                break

        if not filled:
            page.get_by_placeholder("Search", exact=False).first.fill(QUERY)
            print("filled via placeholder")

        page.screenshot(path=str(OUT / "harvest_debug_before_search.png"))

        # Click search
        for sel in ["button:has-text('Search')", "input[type='submit']", "[type='submit']"]:
            loc = page.locator(sel)
            if loc.count():
                loc.first.click()
                print("clicked", sel)
                break

        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT / "harvest_debug_after_search.png"))
        (OUT / "harvest_debug_after_search.html").write_text(page.content(), encoding="utf-8")

        # Direct results URL attempt
        page.goto(
            f"{BASE}/results?department=RP&searchType=quickSearch&searchQuery=mineral+deed",
            wait_until="networkidle",
            timeout=90000,
        )
        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT / "harvest_debug_results_url.png"))
        (OUT / "harvest_debug_results_url.html").write_text(page.content(), encoding="utf-8")

        text = page.inner_text("body")
        print("body text sample:", text[:1500])

        tables = page.locator("table")
        print("tables", tables.count())
        if tables.count():
            print("table0:", tables.first.inner_text()[:2000])

        browser.close()

    (OUT / "harvest_debug_api.json").write_text(json.dumps(api_hits, indent=2), encoding="utf-8")
    print("api hits", len(api_hits))
    for h in api_hits[:10]:
        print(h["url"], h["len"])


if __name__ == "__main__":
    main()
