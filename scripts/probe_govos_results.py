import re
import requests
import pandas as pd
from pathlib import Path

OUT = Path("data/samples")
base = "https://reeves.tx.publicsearch.us"
urls = [
    f"{base}/results?department=RP&searchType=quickSearch&searchQuery=mineral+deed",
    f"{base}/results?department=RP&searchType=advancedSearch&grantorGrantee=mineral",
    f"{base}/?searchQuery=mineral+deed&department=RP",
]
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
for url in urls:
    r = s.get(url, timeout=90)
    print("\nURL", url)
    print("status", r.status_code, "len", len(r.text))
    # look for document numbers / grantor in HTML
    docs = re.findall(r'"docNum(?:ber)?"\s*:\s*"(\d+)"', r.text)
    grantors = re.findall(r'"grantor[^"]*"\s*:\s*"([^"]{3,80})"', r.text, re.I)
    parties = re.findall(r'"name"\s*:\s*"([^"]{3,80})"', r.text)
    rec_dates = re.findall(r'"recordedDate"\s*:\s*"([^"]+)"', r.text)
    print("docNums", len(docs), docs[:5])
    print("grantors", len(grantors), grantors[:5])
    print("parties", len(parties), parties[:5])
    print("dates", len(rec_dates), rec_dates[:5])
    if docs or grantors:
        rows = []
        for i in range(min(25, max(len(docs), len(grantors), 1))):
            rows.append({
                "doc_number": docs[i] if i < len(docs) else "",
                "party": (grantors or parties)[i] if i < len(grantors or parties) else "",
                "recorded_date": rec_dates[i] if i < len(rec_dates) else "",
                "source_url": url,
            })
        pd.DataFrame(rows).to_csv(OUT / "courthouse_reeves_mineral_sample.csv", index=False)
        print("SAVED", len(rows), "rows")
        break
