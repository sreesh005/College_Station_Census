import re
import requests

html = requests.get("https://reeves.tx.publicsearch.us", timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
for term in ["searchDomain", "apiEndpoint", "searchService", "documentsPath", "koSearch", "services", "graphql", "elastic", "algolia", "/v1/", "search-public"]:
    hits = re.findall(rf'.{{0,40}}{re.escape(term)}.{{0,120}}', html)
    if hits:
        print(f"\n{term} ({len(hits)})")
        for h in hits[:5]:
            print(" ", h.replace("\n", " ")[:160])
