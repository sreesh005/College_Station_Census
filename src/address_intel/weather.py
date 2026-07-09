"""Current weather and recent climate via Open-Meteo (free, no API key)."""

from __future__ import annotations

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(latitude: float, longitude: float) -> dict:
    """Return current conditions and today's high/low for a point."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "America/Chicago",
        "forecast_days": 1,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    current = payload.get("current", {})
    daily = payload.get("daily", {})
    return {
        "temp_f": current.get("temperature_2m"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precip_in": current.get("precipitation"),
        "wind_mph": current.get("wind_speed_10m"),
        "weather_code": current.get("weather_code"),
        "high_f": (daily.get("temperature_2m_max") or [None])[0],
        "low_f": (daily.get("temperature_2m_min") or [None])[0],
        "precip_today_in": (daily.get("precipitation_sum") or [None])[0],
        "source": "Open-Meteo",
    }


def weather_label(code: int | None) -> str:
    mapping = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        61: "Rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Snow",
        80: "Rain showers",
        95: "Thunderstorm",
    }
    if code is None:
        return "Unknown"
    return mapping.get(code, f"Code {code}")
