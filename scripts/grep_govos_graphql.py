import re
import requests

base = "https://reeves.tx.publicsearch.us"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
home = s.get(base, timeout=60).text
client = re.search(r'src="(/client\.[^"]+\.js)"', home).group(1)
js = s.get(base + client, timeout=60).text

for term in ["workspaceID", "graphql", "GraphQL", "ko-search", "searchService", "query E", "operationName"]:
    idx = 0
    found = 0
    while found < 5:
        i = js.find(term, idx)
        if i < 0:
            break
        print(f"\n=== {term} @ {i} ===")
        print(js[max(0, i - 120) : i + 200])
        idx = i + len(term)
        found += 1

# try graphql endpoint
for path in ["/graphql", "/api/graphql", "/ko-search/graphql"]:
    r = s.post(base + path, json={"query": "{ __typename }"}, timeout=20)
    print(path, r.status_code, r.text[:100])
