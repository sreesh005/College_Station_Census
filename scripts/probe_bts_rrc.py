import re

import requests

# BTS - avoid PowerShell $ escaping by using requests params dict
r = requests.get(
    "https://data.transportation.gov/resource/8j5p-a5aj.json",
    params={"$limit": "3"},
    timeout=180,
)
print("BTS limit only:", r.status_code, r.text[:500])

r = requests.get(
    "https://data.transportation.gov/resource/8j5p-a5aj.json",
    params={"$limit": "5", "$where": "stateid='48'"},
    timeout=180,
)
print("BTS TX:", r.status_code, r.text[:500])

# RRC - parse MFT HTML for download endpoints
page = requests.get(
    "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
    timeout=120,
).text
patterns = [
    r"https://mft\.rrc\.texas\.gov[^\"'\\s]+",
    r"/webclient/[^\"'\\s]+",
    r"api113[^\"'\\s]{0,80}",
]
for pat in patterns:
    hits = sorted(set(re.findall(pat, page)))[:8]
    if hits:
        print("pattern", pat[:30], hits)

# Try GoDrive public share download patterns
base = "https://mft.rrc.texas.gov"
candidates = [
    f"{base}/webclient/godrive/PublicShare/1eb94d66-461d-4114-93f7-b4bc04a70674/api113.dbf",
    f"{base}/link/1eb94d66-461d-4114-93f7-b4bc04a70674/api113.dbf",
    f"{base}/link/1eb94d66-461d-4114-93f7-b4bc04a70674/file/api113.dbf",
]
for url in candidates:
    r = requests.get(url, timeout=60, stream=True)
    print("RRC GET", url, r.status_code, r.headers.get("content-type"), r.headers.get("content-length"))
