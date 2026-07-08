"""Download RRC MFT file via PrimeFaces partial/ajax POST and save sample."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
ACTION = "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def mft_ajax_download(share_url: str, filename: str, dest: Path) -> dict:
    s = requests.Session()
    s.headers.update(HEADERS)
    html = s.get(share_url, timeout=120).text
    idx = html.find(filename)
    if idx < 0:
        return {"ok": False, "error": "file not in listing"}
    chunk = html[max(0, idx - 400) : idx + 100]
    link = re.search(r'id="(fileTable:\d+:j_id_\w+)"', chunk)
    vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if not link or not vs:
        return {"ok": False, "error": "parse failed"}

    link_id = link.group(1)
    data = {
        "fileList": "fileList",
        "javax.faces.ViewState": vs.group(1),
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": link_id,
        "javax.faces.partial.execute": link_id,
        "javax.faces.partial.render": "@all",
        link_id: link_id,
    }
    r = s.post(ACTION, data=data, timeout=300, headers={**HEADERS, "Referer": share_url})
    if r.content[:4] == b"<?xm" or len(r.content) < 1000:
        return {"ok": False, "bytes": len(r.content), "preview": r.content[:80].decode("latin-1", errors="replace")}
    dest.write_bytes(r.content)
    return {"ok": True, "bytes": len(r.content), "path": str(dest), "link_id": link_id}


def dbf_to_csv(dbf_path: Path, csv_path: Path, n: int = 100) -> int:
    from dbfread import DBF

    table = DBF(str(dbf_path), encoding="latin-1", char_decode_errors="replace")
    df = pd.DataFrame(list(table)[:n])
    df.to_csv(csv_path, index=False)
    return len(df)


def main() -> None:
    share = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
    dbf = OUT / "rrc_api165_midland.dbf"
    result = mft_ajax_download(share, "api165.dbf", dbf)
    if result.get("ok"):
        csv = OUT / "rrc_midland_wells_sample.csv"
        try:
            result["csv_rows"] = dbf_to_csv(dbf, csv)
            result["csv_path"] = str(csv)
        except Exception as exc:
            result["csv_error"] = str(exc)
    (OUT / "mft_ajax_download.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
