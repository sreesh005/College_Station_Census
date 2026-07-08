"""MFT download via correct PublicGoDrive.xhtml form action."""
import json
import re
from pathlib import Path

import requests

OUT = Path("data/samples")
OUT.mkdir(parents=True, exist_ok=True)
SHARE = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
ACTION = "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def download(filename: str, max_bytes: int | None = None) -> dict:
    s = requests.Session()
    s.headers.update(HEADERS)
    html = s.get(SHARE, timeout=120).text
    block = re.search(
        rf'(<tr[^>]*data-ri="\d+"[^>]*>.*?{re.escape(filename)}.*?</tr>)',
        html,
        re.S,
    )
    if not block:
        return {"ok": False, "error": "row not found"}
    row = block.group(1)
    link = re.search(r'id="(fileTable:\d+:j_id_\w+)"', row)
    vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if not link or not vs:
        return {"ok": False, "error": "parse failed"}
    link_id = link.group(1)
    data = {"fileList": "fileList", "javax.faces.ViewState": vs.group(1), link_id: link_id}
    r = s.post(ACTION, data=data, timeout=300, stream=True, headers={**HEADERS, "Referer": SHARE})
    chunks, total = [], 0
    for chunk in r.iter_content(1024 * 256):
        if chunk:
            chunks.append(chunk)
            total += len(chunk)
        if max_bytes and total >= max_bytes:
            break
    content = b"".join(chunks)
    ok = content[:4] != b"<?xm" and total > 500
    info = {"ok": ok, "filename": filename, "bytes": total, "ctype": r.headers.get("content-type")}
    if ok:
        dest = OUT / filename.replace("/", "_")
        dest.write_bytes(content)
        info["path"] = str(dest)
        info["magic"] = content[:4].hex()
    else:
        info["preview"] = content[:150].decode("latin-1", errors="replace")
    return info


def main() -> None:
    results = {
        "api165": download("api165.dbf"),
        "api011": download("api011.dbf"),
        "permit": download("dp_drilling_permit_pending_20200903110806.txt"),
        "wellbore_gz": download("dbf900.txt.gz", max_bytes=3_000_000),
    }
    print(json.dumps(results, indent=2))
    (OUT / "harvest_mft_fixed.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
