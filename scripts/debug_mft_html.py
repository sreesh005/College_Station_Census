import re
import requests

url = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
html = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"}).text
idx = html.find("api165.dbf")
print("idx", idx)
print(html[idx - 300 : idx + 200])
# all data-ri near api165
for m in re.finditer(r"api165\.dbf", html):
    start = max(0, m.start() - 500)
    chunk = html[start : m.start() + 50]
    ri = re.findall(r'data-ri="(\d+)"', chunk)
    print("nearest ri", ri[-1] if ri else None)

# form details
form = re.search(r'<form[^>]*id="fileList"[^>]*action="([^"]*)"', html)
print("form action", form.group(1) if form else None)
print("form method", re.search(r'id="fileList"[^>]*method="([^"]*)"', html))
