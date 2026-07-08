"""One-off probes for failing sources."""
import re

import requests

# FHWA county_code variants
url = "https://geo.dot.gov/server/rest/services/Hosted/Texas_2018_PR/FeatureServer/0/query"
for where in ["county_code=113", "county_code=48113", "county_code IN (113,439,85,121,397)"]:
    r = requests.get(
        url,
        params={"where": where, "outFields": "county_code,aadt,route_id", "resultRecordCount": 3, "f": "json"},
        timeout=60,
    )
    print("FHWA", where, "->", len(r.json().get("features", [])))

# BTS county summary
r = requests.get(
    "https://data.transportation.gov/resource/8j5p-a5aj.json",
    params={"$limit": 5, "$where": "stateid='48' AND countyid='113'"},
    timeout=60,
)
print("BTS county summary", r.status_code, r.text[:500])

# BLM TX filter
for where in ["ADMIN_STATE='TX'", "GEO_STATE='TX'"]:
    r = requests.get(
        blm + "/query",
        params={"where": where, "outFields": "CSE_NR,RCRD_ACRS,ADMIN_STATE,GEO_STATE", "resultRecordCount": 3, "returnGeometry": "false", "returnCountOnly": "true", "f": "json"},
        timeout=90,
    )
    print("BLM count", where, r.json())

# RRC download URL pattern from HTML
r = requests.get("https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674", timeout=60)
for m in re.findall(r"(https?://[^\"']+api113[^\"']*)", r.text):
    print("RRC url", m[:120])
for m in re.findall(r"download[^\"']*api113[^\"']*", r.text, re.I)[:3]:
    print("RRC dl", m[:120])
# try common MFT download path
for path in [
    "https://mft.rrc.texas.gov/webclient/godrive/PublicShare/1eb94d66-461d-4114-93f7-b4bc04a70674/api113.dbf",
    "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674/download/api113.dbf",
]:
    r = requests.head(path, timeout=30, allow_redirects=True)
    print("RRC try", path, r.status_code, r.headers.get("content-type"))

# BLM sample attrs + all fields
blm = "https://gis.blm.gov/nlsdb/rest/services/HUB/BLM_Natl_MLRS_Oil_and_Gas_Leases/FeatureServer/0"
r = requests.get(blm, params={"f": "json"}, timeout=60)
print("BLM all fields:", [f["name"] for f in r.json().get("fields", [])])
r = requests.get(
    blm + "/query",
    params={"where": "1=1", "outFields": "*", "resultRecordCount": 3, "returnGeometry": "false", "f": "json"},
    timeout=90,
)
for feat in r.json().get("features", []):
    print("BLM sample", feat["attributes"])

# RRC list MFT page
r = requests.get("https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674", timeout=60)
print("RRC page len", len(r.text))
for m in sorted(set(re.findall(r"api\d+\.dbf", r.text, re.I))):
    print("RRC file", m)
