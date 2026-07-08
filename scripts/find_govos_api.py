"""Find GovOS search API host from HTML + JS bundles."""
import json
import re
import requests

COUNTY = "reeves"
base = f"https://{COUNTY}.tx.publicsearch.us"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
html = s.get(base, timeout=60).text

# Config blob around tenant
for term in ["searchApi", "apiBase", "apiHost", "koSearch", "elastic", "documentsUrl", "baseUrl", "graphql", "aws", "execute-api"]:
    hits = re.findall(rf'.{{0,30}}{term}.{{0,80}}', html, re.I)
    if hits:
        print(f"\n=== HTML {term} ===")
        for h in hits[:8]:
            print(h[:140])

scripts = re.findall(r'src="(/[^"]+\.js)"', html)
print("\nscripts", scripts)
for script in scripts:
    if "client" in script or script.startswith("/0."):
        js = s.get(base + script, timeout=60).text
        for pat in [
            r"https://[a-zA-Z0-9.-]+\.amazonaws\.com[^\"']*",
            r"https://[a-zA-Z0-9.-]+\.execute-api\.[a-z0-9.-]+[^\"']*",
            r'"(/v\d+/[^"]+)"',
            r"search[^\"']*\.(?:amazonaws|cloudfront)[^\"']*",
        ]:
            hits = sorted(set(re.findall(pat, js)))
            if hits:
                print(f"\n{script} {pat[:40]}:", hits[:10])
