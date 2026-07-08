"""Small-sample harvest: RRC + courthouse index probes."""
from __future__ import annotations

import gzip
import io
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "location-intelligence-research/1.0 (noncommercial pilot)"}


def try_download(url: str, dest: Path, max_bytes: int | None = None) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=120, stream=True)
    info = {"url": url, "status": r.status_code, "content_type": r.headers.get("content-type")}
    if r.status_code != 200:
        info["error"] = r.text[:200]
        return info
    data = b""
    for chunk in r.iter_content(1024 * 256):
        if chunk:
            data += chunk
        if max_bytes and len(data) >= max_bytes:
            break
    dest.write_bytes(data)
    info["bytes"] = len(data)
    info["path"] = str(dest)
    return info


def probe_govos_search(county_subdomain: str, query: str) -> dict:
    """GovOS React apps often expose search via internal API - probe common paths."""
    base = f"https://{county_subdomain}.tx.publicsearch.us"
    session = requests.Session()
    session.headers.update(HEADERS)
    home = session.get(base, timeout=30)
    # Extract script bundles
    scripts = re.findall(r'src="(/[^"]+\.js)"', home.text)
    api_hits = []
    for script in scripts[:5]:
        try:
            js = session.get(base + script, timeout=30).text
            for m in re.findall(r"https://[^\"']+api[^\"']+", js):
                api_hits.append(m)
            for m in re.findall(r'"/[^"]*search[^"]*"', js)[:10]:
                api_hits.append(m)
        except Exception:
            pass
    return {
        "county": county_subdomain,
        "home_status": home.status_code,
        "script_count": len(scripts),
        "api_hints": sorted(set(api_hits))[:15],
    }


def main() -> None:
    results: dict = {}

    # RRC - try direct file URLs from known MFT folders (stream first 2MB)
    rrc_tests = [
        (
            "https://mft.rrc.texas.gov/link/b070ce28-5c58-4fe2-9eb7-8b70befb7af9/dbf900.txt.gz",
            OUT / "rrc_dbf900_head.gz",
            2_000_000,
        ),
        (
            "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674/api165.dbf",
            OUT / "rrc_api165_sample.dbf",
            500_000,
        ),
    ]
    results["rrc"] = []
    for url, dest, cap in rrc_tests:
        results["rrc"].append(try_download(url, dest, max_bytes=cap))

    # Parse head of wellbore if gzip works
    gz_path = OUT / "rrc_dbf900_head.gz"
    if gz_path.exists() and gz_path.stat().st_size > 100:
        try:
            raw = gzip.decompress(gz_path.read_bytes())
            lines = raw.decode("latin-1", errors="replace").splitlines()[:20]
            (OUT / "rrc_dbf900_sample_lines.txt").write_text("\n".join(lines), encoding="utf-8")
            results["rrc_wellbore_sample_lines"] = len(lines)
        except Exception as exc:
            results["rrc_wellbore_parse_error"] = str(exc)

    # GovOS counties
    results["govos"] = [
        probe_govos_search("midland", "mineral deed"),
        probe_govos_search("tarrant", "oil gas lease"),
        probe_govos_search("reeves", "mineral"),
    ]

    # Harris - try RP search endpoint patterns
    harris_urls = [
        "https://cclerk.hctx.net/Applications/WebSearch/RP.aspx",
        "https://cclerk.hctx.net/Applications/WebSearch/Home.aspx",
    ]
    results["harris"] = []
    for url in harris_urls:
        r = requests.get(url, headers=HEADERS, timeout=30)
        results["harris"].append({"url": url, "status": r.status_code, "len": len(r.text)})

    out_json = OUT / "harvest_probe_results.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
