import json
import re
import requests

base = "https://reeves.tx.publicsearch.us"
html = requests.get(base, timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
# Find large JSON state blob
for pat in [
    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;",
    r"__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;",
    r'"tenant":\{"code":"48389"[^}]*\}[^}]*\}',
]:
    m = re.search(pat, html, re.S)
    if m:
        print("matched", pat[:40], "len", len(m.group(0)[:5000]))

# Extract tenant block context
idx = html.find('"tenant":{"code":"48389"')
print(html[idx - 500 : idx + 1500])
