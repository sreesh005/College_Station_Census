import re

import requests

page = requests.get(
    "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
    timeout=120,
).text
idx = page.find("api113")
print(page[idx - 500 : idx + 500])

# statewide ASCII link from RRC datasets page
r = requests.get(
    "https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/",
    timeout=60,
)
for m in re.findall(r"https://mft\.rrc\.texas\.gov/link/[a-f0-9-]+", r.text):
    print("MFT link", m)
