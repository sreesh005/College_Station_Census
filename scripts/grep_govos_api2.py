import re
import requests

base = "https://reeves.tx.publicsearch.us"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
home = s.get(base, timeout=60).text
client = re.search(r'src="(/client\.[^"]+\.js)"', home).group(1)
js = s.get(base + client, timeout=60).text

for term in ["FETCH_DOCUMENTS", "baseURL", "apiUrl", "API_URL", "search-api", "documents?", "/documents"]:
    print(f"\n==== {term} ====")
    for m in re.finditer(re.escape(term), js):
        print(js[max(0, m.start() - 80) : m.start() + 180])
        break

# Search vendor dll too
vendor = re.search(r'src="(/vendor[^"]+\.dll\.js)"', home)
if vendor:
    vjs = s.get(base + vendor.group(1), timeout=60).text
    for term in ["https://", "search", "documents"]:
        hits = re.findall(r"https://[a-zA-Z0-9._/-]{10,80}", vjs)
        if hits:
            print("\nvendor urls sample:", sorted(set(hits))[:15])
