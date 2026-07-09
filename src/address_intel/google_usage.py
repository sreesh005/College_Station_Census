"""Track Google Places API usage to stay within free-tier limits."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT, get_api_key

USAGE_PATH = ROOT / "data" / "google_places_usage.json"

# Nearby Search Pro: 5,000 free calls/month (Google Maps Platform, March 2025+).
DEFAULT_MONTHLY_CAP = 4500
ABSOLUTE_MONTHLY_MAX = 5000  # never exceed free tier via env misconfiguration
DEFAULT_SESSION_CAP = 30  # max API calls per browser session (~10 new addresses)
SESSION_ABSOLUTE_MAX = 100  # session cap cannot exceed this via env


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load() -> dict:
    if not USAGE_PATH.exists():
        return {}
    try:
        with open(USAGE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _int_env(name: str, default: int, absolute_max: int | None = None) -> int:
    raw = os.getenv(name) or get_api_key(name)
    if raw:
        try:
            value = max(1, int(str(raw).strip()))
            if absolute_max is not None:
                return min(value, absolute_max)
            return value
        except ValueError:
            pass
    return default


def monthly_cap() -> int:
    return _int_env("GOOGLE_PLACES_MONTHLY_CAP", DEFAULT_MONTHLY_CAP, ABSOLUTE_MONTHLY_MAX)


def session_cap() -> int:
    return _int_env("GOOGLE_PLACES_SESSION_CAP", DEFAULT_SESSION_CAP, SESSION_ABSOLUTE_MAX)


def calls_per_amenity_fetch() -> int:
    """Number of Nearby Search calls per address lookup (batched)."""
    return 3


def get_usage() -> dict:
    data = _load()
    month = _month_key()
    entry = data.get(month, {})
    used = int(entry.get("calls", 0))
    cap = monthly_cap()
    return {
        "month": month,
        "calls_used": used,
        "calls_cap": cap,
        "calls_remaining": max(0, cap - used),
        "at_limit": used >= cap,
        "session_cap": session_cap(),
        "absolute_max": ABSOLUTE_MONTHLY_MAX,
    }


def _limit_message(usage: dict, needed: int) -> str:
    return (
        f"Monthly Google Places cap reached ({usage['calls_used']:,} / {usage['calls_cap']:,} calls). "
        f"Need {needed} more. Resets on the 1st of next month. "
        "Hard ceiling is 5,000 free tier — also set a quota in Google Cloud Console."
    )


def can_fetch_amenities(session_calls_used: int = 0) -> tuple[bool, str | None]:
    usage = get_usage()
    needed = calls_per_amenity_fetch()
    if usage["calls_remaining"] < needed:
        return False, _limit_message(usage, needed)
    if session_calls_used + needed > session_cap():
        return False, (
            f"Session Google Places cap reached ({session_calls_used:,} / {session_cap():,} calls). "
            "Refresh the page to start a new session, or raise GOOGLE_PLACES_SESSION_CAP in .env."
        )
    return True, None


def reserve_calls(count: int, session_calls_used: int = 0) -> tuple[bool, str | None]:
    """
    Atomically reserve API calls BEFORE hitting Google.
    Returns False if monthly or session cap would be exceeded.
    """
    if count <= 0:
        return True, None

    usage = get_usage()
    if usage["calls_remaining"] < count:
        return False, _limit_message(usage, count)
    if session_calls_used + count > session_cap():
        return False, (
            f"Session Google Places cap reached ({session_calls_used:,} / {session_cap():,} calls). "
            "Refresh the page to start a new session."
        )

    data = _load()
    month = _month_key()
    entry = data.setdefault(month, {"calls": 0})
    used = int(entry.get("calls", 0))
    cap = monthly_cap()
    entry["calls"] = min(cap, used + count)  # hard clamp — never log above cap
    _save(data)
    return True, None


def record_calls(count: int) -> dict:
    """Legacy helper; prefer reserve_calls before requests."""
    reserve_calls(count)
    return get_usage()
