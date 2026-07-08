import re
import requests

base = "https://reeves.tx.publicsearch.us"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
home = s.get(base, timeout=60).text
chunks = re.findall(r'src="(/0\.[^"]+\.js)"', home)
print("chunks", chunks)
for chunk in chunks:
    js = s.get(base + chunk, timeout=60).text
    hosts = sorted(set(re.findall(r"https://[a-zA-Z0-9.-]+(?:amazonaws|execute-api|cloudfront|kofile|govos)[a-zA-Z0-9./_-]*", js)))
    if hosts:
        print(chunk, hosts[:20])
    for term in ["execute-api", "amazonaws.com", "search-api", "documents/search", "apiBase", "API_BASE"]:
        if term in js:
            i = js.find(term)
            print(chunk, term, js[max(0,i-100):i+150])

# probe fetch-document-images
r = s.post(base + "/fetch-document-images", json={"ids": [1]}, timeout=20)
print("fetch-doc-images", r.status_code, r.text[:150])
