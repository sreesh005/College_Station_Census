from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = ROOT / "exports"
SQLITE_PATH = DATA_DIR / "location_intelligence.db"

load_dotenv(ROOT / ".env")


def refresh_env() -> None:
    """Re-read .env so key changes apply without restarting Streamlit."""
    load_dotenv(ROOT / ".env", override=True)


def load_pilot_config() -> dict:
    with open(ROOT / "config" / "pilot_geography.json", encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _from_streamlit_secrets(name: str) -> str | None:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return None


def get_api_key(name: str) -> str | None:
    refresh_env()
    value = os.getenv(name) or _from_streamlit_secrets(name)
    if not value:
        return None
    value = value.strip().strip('"').strip("'")
    if value.startswith("\ufeff"):
        value = value.lstrip("\ufeff")
    if value.startswith("http"):
        return None
    if value.lower() in {
        "your_key_here",
        "changeme",
        "replace_me",
        "your_census_key_here",
        "your_fred_key_here",
        "your_data_gov_key_here",
        "your_google_maps_key_here",
    }:
        return None
    return value


def get_google_maps_api_key() -> str | None:
    """GOOGLE_MAPS_API_KEY plus common alternate names."""
    for name in ("GOOGLE_MAPS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_PLACES_API_KEY"):
        key = get_api_key(name)
        if key:
            return key
    return None


def missing_api_keys() -> list[str]:
    required = ("CENSUS_API_KEY", "FRED_API_KEY", "DATA_GOV_API_KEY")
    return [name for name in required if not get_api_key(name)]
