"""Validate API keys without printing secret values."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _check(name: str) -> tuple[bool, str]:
    value = os.getenv(name, "").strip().strip('"').strip("'")
    if not value:
        return False, "missing"

    if name == "CENSUS_API_KEY":
        response = requests.get(
            "https://api.census.gov/data/2023/acs/acs5",
            params={"get": "NAME", "for": "us:1", "key": value},
            timeout=60,
        )
        if "Invalid Key" in response.text:
            return False, "invalid or not activated yet"
        if "Missing Key" in response.text:
            return False, "missing in request"
        return True, "ok"

    if name == "FRED_API_KEY":
        response = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": "GNPCA", "api_key": value, "file_type": "json", "limit": 1},
            timeout=60,
        )
        return response.status_code == 200, f"HTTP {response.status_code}"

    if name == "DATA_GOV_API_KEY":
        response = requests.get(
            "https://api.usa.gov/crime/fbi/sapi/",
            params={"api_key": value},
            timeout=60,
        )
        return response.status_code == 200, f"HTTP {response.status_code}"

    return False, "unknown key name"


def main() -> int:
    all_ok = True
    for key_name in ("CENSUS_API_KEY", "FRED_API_KEY", "DATA_GOV_API_KEY"):
        ok, detail = _check(key_name)
        print(f"{key_name}: {'PASS' if ok else 'FAIL'} ({detail})")
        all_ok = all_ok and ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
