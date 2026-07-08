import re

import requests

page = requests.get(
    "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
    timeout=120,
).text

# Extract row keys for pilot county files
for county in ["085", "113", "121", "397", "439"]:
    pat = rf"data-rk=\"(\d+)\"[^>]*>.*?api{county}\.dbf"
    m = re.search(pat, page, re.S)
    print(f"api{county}.dbf rk=", m.group(1) if m else None)

# Search for download endpoints in page
for pat in ["download", "Download", "fileId", "resourceKey", "PublicShare"]:
    hits = sorted(set(re.findall(rf"{pat}[A-Za-z]*[^\"'\\s]{{0,60}}", page)))[:6]
    if hits:
        print(pat, hits[:4])

# Try GoDrive download with resource key from api113
m = re.search(r'data-rk="(\d+)"[^>]*>.*?api113\.dbf', page, re.S)
if m:
    rk = m.group(1)
    session = requests.Session()
    session.get("https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674", timeout=120)
    for url, data in [
        (
            "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml",
            {"javax.faces.partial.ajax": "true"},
        ),
        (
            f"https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
            None,
        ),
    ]:
        print("try", url)
