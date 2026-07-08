import re
import requests

base = "https://reeves.tx.publicsearch.us"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
home = s.get(base, timeout=60).text
client = re.search(r'src="(/client\.[^"]+\.js)"', home).group(1)
js = s.get(base + client, timeout=60).text
print("js len", len(js))
for pat in [r'"/[^"]{3,80}"', r"fetch\([^)]+\)", r"axios\.[a-z]+\([^)]+\)", r"search[A-Za-z]*:\s*\"[^\"]+\""]:
    hits = sorted(set(re.findall(pat, js)))
    interesting = [h for h in hits if any(k in h.lower() for k in ("search", "api", "result", "query", "record"))]
    if interesting:
        print("\nPAT", pat[:30], "count", len(interesting))
        for h in interesting[:20]:
            print(" ", h[:120])
