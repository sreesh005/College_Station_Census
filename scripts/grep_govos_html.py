import json
import re
import requests

for county in ["reeves", "midland", "tarrant"]:
    base = f"https://{county}.tx.publicsearch.us"
    html = requests.get(base, timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
    print("\n===", county, "len", len(html), "===")
    for pat in [
        r"window\.__[A-Z_]+__\s*=\s*(\{.*?\});",
        r"apiHost[^,\n]{0,120}",
        r"tenant[^,\n]{0,120}",
        r"ko-search[^,\n]{0,120}",
        r"searchApi[^,\n]{0,120}",
        r"REACT_APP_[A-Z_]+",
    ]:
        hits = re.findall(pat, html, re.I)
        if hits:
            print(pat[:40], hits[:3])

    # embedded JSON scripts
    for m in re.finditer(r"<script[^>]*>(\{.*?\})</script>", html[:50000], re.S):
        txt = m.group(1)[:200]
        if "api" in txt.lower() or "tenant" in txt.lower():
            print("script json", txt)
