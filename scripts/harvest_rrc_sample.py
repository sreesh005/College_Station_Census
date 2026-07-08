"""Download small RRC samples via MFT PrimeFaces (fixed row match)."""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def mft_download(share_url: str, filename: str, max_bytes: int | None = None) -> dict:
    s = requests.Session()
    s.headers.update(HEADERS)
    html = s.get(share_url, timeout=120).text
    block = re.search(
        rf'(<tr[^>]*data-ri="\d+"[^>]*>.*?{re.escape(filename)}.*?</tr>)',
        html,
        re.S,
    )
    if not block:
        return {"ok": False, "error": f"{filename} not in listing"}
    row_html = block.group(1)
    ri = re.search(r'data-ri="(\d+)"', row_html)
    link = re.search(r'id="(fileTable:\d+:j_id_\w+)"', row_html)
    vs = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if not (ri and link and vs):
        return {"ok": False, "error": "parse failed"}

    link_id = link.group(1)
    data = {"fileList": "fileList", "javax.faces.ViewState": vs.group(1), link_id: link_id}
    r = s.post(share_url, data=data, timeout=300, stream=True)
    chunks = []
    total = 0
    for chunk in r.iter_content(1024 * 256):
        if chunk:
            chunks.append(chunk)
            total += len(chunk)
        if max_bytes and total >= max_bytes:
            break
    content = b"".join(chunks)
    is_binary = content[:4] != b"<?xm" and total > 500
    info = {
        "ok": is_binary,
        "filename": filename,
        "row_index": ri.group(1),
        "bytes": total,
        "ctype": r.headers.get("content-type"),
    }
    if is_binary:
        dest = OUT / filename.replace("/", "_")
        dest.write_bytes(content)
        info["path"] = str(dest)
    else:
        info["preview"] = content[:120].decode("latin-1", errors="replace")
    return info


def parse_dbf_head(path: Path, n: int = 100):
    try:
        import pandas as pd
        from dbfread import DBF

        table = DBF(str(path), encoding="latin-1", ignore_missing_memos=True, char_decode_errors="replace")
        return pd.DataFrame(list(table)[:n])
    except Exception:
        return None


def main() -> None:
    import pandas as pd

    summary: dict = {}

    # Small county DBF - Midland
    r1 = mft_download(
        "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674",
        "api165.dbf",
    )
    summary["midland_api_dbf"] = r1
    if r1.get("ok"):
        df = parse_dbf_head(Path(r1["path"]), 100)
        if df is not None and not df.empty:
            csv_out = OUT / "rrc_midland_wells_sample.csv"
            df.to_csv(csv_out, index=False)
            summary["midland_wells_rows"] = len(df)
            summary["midland_wells_cols"] = list(df.columns)

    # Small permit pending file
    r2 = mft_download(
        "https://mft.rrc.texas.gov/link/0ad92a65-4212-49a1-98a7-d667a55fb497",
        "dp_drilling_permit_pending_20200903110806.txt",
    )
    summary["permit_pending"] = r2
    if r2.get("ok"):
        text = Path(r2["path"]).read_text(errors="replace")
        preview = "\n".join(text.splitlines()[:30])
        (OUT / "rrc_permit_pending_preview.txt").write_text(preview, encoding="utf-8")

    # Stream first 5MB of compressed full wellbore for line sample
    r3 = mft_download(
        "https://mft.rrc.texas.gov/link/b070ce28-5c58-4fe2-9eb7-8b70befb7af9",
        "dbf900.txt.gz",
        max_bytes=5_000_000,
    )
    summary["wellbore_gz_head"] = r3
    if r3.get("ok"):
        raw = gzip.decompress(Path(r3["path"]).read_bytes())
        lines = raw.decode("latin-1", errors="replace").splitlines()[:50]
        (OUT / "rrc_wellbore_sample_lines.txt").write_text("\n".join(lines), encoding="utf-8")
        summary["wellbore_sample_lines"] = len(lines)

    (OUT / "harvest_rrc_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
