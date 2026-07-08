import re
import requests

base = "https://reeves.tx.publicsearch.us"
js = requests.get(base + "/client.ff70b0c68ed713f9ec0d.js", timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
hosts = sorted(set(re.findall(r"https://[a-zA-Z0-9.-]+\.(?:amazonaws|cloudfront|govos|kofile|publicsearch)[a-zA-Z0-9./_-]*", js)))
print("hosts", len(hosts))
for h in hosts[:30]:
    print(h)

# also look for host strings without https
for pat in [r"search-[a-z-]+\.[a-z.]+\.[a-z]+", r"ko-search[a-zA-Z0-9.-]*", r"\.execute-api\.[^\"']+"]:
    hits = sorted(set(re.findall(pat, js)))
    if hits:
        print("\n", pat, hits[:10])
