"""Probe RRC MFT download variants and GovOS search API."""
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) location-intelligence/1.0"}


def probe_rrc_mft(filename: str = "api165.dbf") -> dict:
    share = "https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674"
    session = requests.Session()
    session.headers.update(HEADERS)
    html = session.get(share, timeout=120).text
    view_state = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    row = re.search(rf'data-ri="(\d+)"[^>]*>.*?{re.escape(filename)}', html, re.S)
    rk = re.search(rf'data-rk="(\d+)"[^>]*>.*?{re.escape(filename)}', html, re.S)
    link = re.search(rf'id="(fileTable:\d+:j_id_\w+)"[^>]*>{re.escape(filename)}', html)
    if not view_state or not row:
        return {"ok": False, "error": "parse failed"}

    ri, link_id = row.group(1), (link.group(1) if link else f"fileTable:{row.group(1)}:j_id_2f")
    rk_val = rk.group(1) if rk else None
    vs = view_state.group(1)
    attempts: list[dict] = []

    payloads = [
        {"fileList": "fileList", "javax.faces.ViewState": vs, link_id: link_id},
        {
            "fileList": "fileList",
            "javax.faces.ViewState": vs,
            "javax.faces.source": link_id,
            "javax.faces.partial.event": "click",
            "javax.faces.partial.ajax": "true",
            link_id: link_id,
        },
    ]
    for i, data in enumerate(payloads):
        r = session.post(share, data=data, timeout=180)
        attempts.append(
            {
                "variant": i,
                "status": r.status_code,
                "ctype": r.headers.get("content-type"),
                "bytes": len(r.content),
                "magic": r.content[:8].hex(),
                "disp": r.headers.get("content-disposition"),
            }
        )
        if r.content[:4] != b"<?xm" and len(r.content) > 1000:
            dest = OUT / f"rrc_{filename.replace('.', '_')}_v{i}.bin"
            dest.write_bytes(r.content)
            attempts[-1]["saved"] = str(dest)

    # Resource-key direct paths seen on GoAnywhere shares
    if rk_val:
        for path in [
            f"{share}/download/{filename}",
            f"https://mft.rrc.texas.gov/webclient/godrive/PublicShare/1eb94d66-461d-4114-93f7-b4bc04a70674/{filename}",
            f"https://mft.rrc.texas.gov/webclient/godrive/download?resourceKey={rk_val}",
            f"https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml?resourceKey={rk_val}",
        ]:
            r = session.get(path, timeout=60, allow_redirects=True)
            attempts.append(
                {
                    "url": path,
                    "status": r.status_code,
                    "bytes": len(r.content),
                    "magic": r.content[:8].hex(),
                    "ctype": r.headers.get("content-type"),
                }
            )

    return {"filename": filename, "row_index": ri, "resource_key": rk_val, "attempts": attempts}


def probe_rrc_text_datasets() -> list[dict]:
    """Try smaller ASCII datasets that may have simpler download flows."""
    pages = [
        "https://mft.rrc.texas.gov/link/0ad92a65-4212-49a1-98a7-d667a55fb497",  # drilling permits pending
        "https://mft.rrc.texas.gov/link/b070ce28-5c58-4fe2-9eb7-8b70befb7af9",  # full wellbore
    ]
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)
    for url in pages:
        html = session.get(url, timeout=120).text
        files = re.findall(r">([^<]+\.(?:txt|csv|gz))</a>", html)[:8]
        results.append({"url": url, "sample_files": files, "html_len": len(html)})
    return results


def probe_govos(county: str = "midland") -> dict:
    base = f"https://{county}.tx.publicsearch.us"
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept": "*/*"})
    home = session.get(base, timeout=30)
    scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', home.text)
    if not scripts:
        scripts = re.findall(r'src="(/[^"]+\.js)"', home.text)
    api_hints: set[str] = set()
    for script in scripts[:12]:
        try:
            js = session.get(base + script, timeout=30).text
            for pat in [
                r'"(/api/[^"]+)"',
                r'"(/search/[^"]+)"',
                r"https://[^\"']*govos[^\"']*",
                r"https://[^\"']*kofile[^\"']*",
                r"REACT_APP_[A-Z_]+",
            ]:
                api_hints.update(re.findall(pat, js))
        except Exception:
            pass

    # Try ko-search style endpoints discovered in many GovOS tenants
    search_tests = []
    candidates = [
        (f"{base}/api/search/quick", {"query": "mineral deed", "department": "RP", "limit": 25}),
        (f"{base}/api/v1/search", {"searchTerm": "mineral deed", "department": "RP"}),
        (f"https://api.publicsearch.us/{county}.tx/search", {"query": "mineral deed"}),
    ]
    for url, payload in candidates:
        for method in ("GET", "POST"):
            try:
                if method == "GET":
                    r = session.get(url, params=payload, timeout=20)
                else:
                    r = session.post(url, json=payload, timeout=20)
                search_tests.append(
                    {
                        "url": url,
                        "method": method,
                        "status": r.status_code,
                        "ctype": r.headers.get("content-type"),
                        "preview": r.text[:120],
                    }
                )
            except Exception as exc:
                search_tests.append({"url": url, "method": method, "error": str(exc)})

    return {
        "county": county,
        "home_status": home.status_code,
        "scripts": scripts[:8],
        "api_hints": sorted(api_hints)[:30],
        "search_tests": search_tests,
    }


def probe_harris_rp_search() -> dict:
    """Harris County uses ASP.NET WebSearch - probe form endpoints."""
    url = "https://cclerk.hctx.net/Applications/WebSearch/RP.aspx"
    session = requests.Session()
    session.headers.update(HEADERS)
    r = session.get(url, timeout=30)
    viewstate = re.search(r'id="__VIEWSTATE" value="([^"]+)"', r.text)
    eventval = re.search(r'id="__EVENTVALIDATION" value="([^"]+)"', r.text)
    if not viewstate:
        return {"ok": False, "status": r.status_code, "error": "no viewstate"}

    data = {
        "__VIEWSTATE": viewstate.group(1),
        "__EVENTVALIDATION": eventval.group(1) if eventval else "",
        "ctl00$ContentPlaceHolder1$txtGrantorGrantee": "MINERAL",
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
    }
    r2 = session.post(url, data=data, timeout=60)
    rows = re.findall(r"ctl00_ContentPlaceHolder1_gvResults[^>]*>(.*?)</table>", r2.text, re.S)
    tr_count = len(re.findall(r"<tr", r2.text))
    return {
        "ok": True,
        "post_status": r2.status_code,
        "result_tables": len(rows),
        "tr_count": tr_count,
        "preview": re.sub(r"\s+", " ", r2.text[:1500]),
    }


def main() -> None:
    summary = {
        "rrc_mft": probe_rrc_mft("api165.dbf"),
        "rrc_mft_small": probe_rrc_mft("api011.dbf"),
        "rrc_text_pages": probe_rrc_text_datasets(),
        "govos_midland": probe_govos("midland"),
        "govos_reeves": probe_govos("reeves"),
        "harris_search": probe_harris_rp_search(),
    }
    out = OUT / "harvest_deep_probe.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
