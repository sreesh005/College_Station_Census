"""Debug MFT PrimeFaces download."""
import re
from pathlib import Path

import requests

URL = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
FILENAME = "api165.dbf"
OUT = Path("data/samples/rrc_api165_midland.dbf")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
html = session.get(URL, timeout=120).text
print("listing bytes", len(html))

view_state = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
row = re.search(rf'data-ri="(\d+)"[^>]*>.*?{re.escape(FILENAME)}', html, re.S)
link = re.search(rf'id="(fileTable:\d+:j_id_\w+)"[^>]*>{re.escape(FILENAME)}', html)
print("view_state", bool(view_state), "row", row.group(1) if row else None, "link", link.group(1) if link else None)

link_id = link.group(1) if link else f"fileTable:{row.group(1)}:j_id_2f"
data = {
    "fileList": "fileList",
    "javax.faces.ViewState": view_state.group(1),
    link_id: link_id,
}

# POST to share URL (form action is typically same page)
resp = session.post(URL, data=data, timeout=180)
print("post status", resp.status_code, "ctype", resp.headers.get("content-type"), "bytes", len(resp.content))
print("magic", resp.content[:16])

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(resp.content)
