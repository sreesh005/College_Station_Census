"""Fixed MFT download with correct row match + GovOS client.js API discovery."""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

OUT = Path("data/samples")
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def download_mft(share_url: str, filename: str) -> dict:
    s = requests.Session()
    s.headers.update(HEADERS)
    html = s.get(share_url, timeout=120).text

    # Match the link row directly (avoid greedy data-ri mismatch)
    block = re.search(
        rf'(<tr[^>]*data-ri="\d+"[^>]*>.*?{re.escape(filename)}.*?</tr>)',
        html,
        re.S,
    )
    if not block:
        return {"ok": False, "error": f"{filename} row not found"}
    row_html = block.group(1)
    ri = re.search(r'data-ri="(\d+)"', row_html)
    rk = re.search(r'data-rk="(\d+)"', row_html)
    link = re.search(r'id="(fileTable:\d+:j_id_\w+)"', row_html)
    vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if not (ri and link and vs):
        return {"ok": False, "error": "missing ri/link/viewstate"}

    link_id = link.group(1)
    data = {
        "fileList": "fileList",
        "javax.faces.ViewState": vs.group(1),
        link_id: link_id,
    }
    r = s.post(share_url, data=data, timeout=180)
    info = {
        "ok": r.content[:4] != b"<?xm" and len(r.content) > 5000,
        "filename": filename,
        "row_index": ri.group(1),
        "resource_key": rk.group(1) if rk else None,
        "bytes": len(r.content),
        "magic": r.content[:4],
        "ctype": r.headers.get("content-type"),
        "cookies": dict(s.cookies),
    }
    if info["ok"]:
        dest = OUT / filename
        dest.write_bytes(r.content)
        info["path"] = str(dest)
    else:
        info["preview"] = r.content[:200].decode("latin-1", errors="replace")
        # Save ajax attempt
        ajax = {
            **data,
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": link_id,
            "javax.faces.partial.execute": link_id,
            "javax.faces.partial.render": "@all",
        }
        r2 = s.post(share_url, data=ajax, timeout=180)
        info["ajax_bytes"] = len(r2.content)
        info["ajax_preview"] = r2.text[:500]
    return info


def grep_client_js(county: str = "midland") -> dict:
    base = f"https://{county}.tx.publicsearch.us"
    s = requests.Session()
    s.headers.update(HEADERS)
    home = s.get(base, timeout=30).text
    client = re.search(r'src="(/client\.[^"]+\.js)"', home)
    if not client:
        return {"error": "no client js"}
    js = s.get(base + client.group(1), timeout=60).text
    patterns = [
        r"https://[a-zA-Z0-9._/-]+search[a-zA-Z0-9._/-]*",
        r'"/[a-zA-Z0-9/_-]*search[a-zA-Z0-9/_-]*"',
        r"ko-search[a-zA-Z0-9._/-]*",
        r"graphql[a-zA-Z0-9._/-]*",
        r"tenantId[^,]{0,80}",
        r"department[^,]{0,80}",
    ]
    hits: dict[str, list[str]] = {}
    for pat in patterns:
        hits[pat] = sorted(set(re.findall(pat, js)))[:15]
    (OUT / f"govos_{county}_client_snip.txt").write_text(js[:8000], encoding="utf-8")
    return {"client": client.group(1), "js_len": len(js), "hits": hits}


def main() -> None:
    results = {
        "api165": download_mft(
            "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
            "api165.dbf",
        ),
        "dbf900_txt": download_mft(
            "https://mft.rrc.texas.gov/link/b070ce28-5c58-4fe2-9eb7-8b70befb7af9",
            "dbf900.txt",
        ),
        "permit_txt": download_mft(
            "https://mft.rrc.texas.gov/link/0ad92a65-4212-49a1-98a7-d667a55fb497",
            "dp_drilling_permit_pending_20200903110806.txt",
        ),
        "govos_js": grep_client_js("midland"),
    }
    (OUT / "harvest_fix_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
