import re
import requests
from html.parser import HTMLParser

SHARE = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
html = requests.get(SHARE, timeout=120, headers={"User-Agent": "Mozilla/5.0"}).text

# Extract all hidden inputs in fileList form
form_match = re.search(r'<form[^>]*id="fileList"[^>]*>(.*?)</form>', html, re.S)
if form_match:
    inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form_match.group(1))
    print("hidden inputs", len(inputs))
    for name, val in inputs[:20]:
        print(name, val[:60] if val else "")

# Cookies from session
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
r = s.get(SHARE, timeout=120)
print("cookies", dict(s.cookies))

# Try POST with all hidden fields + link click
link_id = "fileTable:82:j_id_2f"
data = {name: val for name, val in inputs}
data[link_id] = link_id
data["fileList"] = "fileList"
r2 = s.post(
    "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml",
    data=data,
    timeout=120,
    headers={"Referer": SHARE},
)
print("post2", r2.status_code, len(r2.content), r2.headers.get("content-type"))
print("magic", r2.content[:8])
print("disp", r2.headers.get("content-disposition"))
