import re
import requests

base = "https://reeves.tx.publicsearch.us"
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
home = s.get(base, timeout=60).text
client = re.search(r'src="(/client\.[^"]+\.js)"', home).group(1)
js = s.get(base + client, timeout=60).text

paths = sorted(set(re.findall(r'"(/[a-zA-Z0-9_/-]{3,60})"', js)))
interesting = [p for p in paths if any(k in p.lower() for k in ("search", "doc", "result", "record", "index", "api"))]
print("paths", interesting[:40])

payloads = [
    ("GET", "/results", {"searchQuery": "mineral deed", "department": "RP", "searchType": "quickSearch"}),
    ("GET", "/results", {"q": "mineral deed", "dept": "RP"}),
    ("POST", "/ko-search/documents/search", {"tenantId": "48389", "query": "mineral deed", "limit": 25}),
    ("POST", "/documents/search", {"tenantId": "48389", "searchTerm": "mineral deed"}),
    ("GET", "/search/documents", {"tenantId": "48389", "q": "mineral deed"}),
]
for method, path, params in payloads:
    try:
        if method == "GET":
            r = s.get(base + path, params=params, timeout=30)
        else:
            r = s.post(base + path, json=params, timeout=30)
        print(method, path, r.status_code, r.headers.get("content-type", "")[:40], r.text[:120].replace("\n", " "))
    except Exception as e:
        print(method, path, "ERR", e)
