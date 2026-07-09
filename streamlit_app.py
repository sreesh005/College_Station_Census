"""Dallas–Fort Worth address intelligence dashboard — Streamlit app."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import importlib

import src.config as _config_mod
import src.address_intel.amenities as _amenities_mod
import src.address_intel.google_usage as _google_usage_mod
import src.address_intel.permits_local as _permits_mod
import streamlit_site_selection as _site_selection_mod

importlib.reload(_config_mod)
importlib.reload(_google_usage_mod)
importlib.reload(_amenities_mod)
importlib.reload(_permits_mod)
importlib.reload(_site_selection_mod)

from src.address_intel.amenities import AMENITY_CATEGORIES, fetch_amenities
from src.address_intel.census import fetch_county_acs, fetch_tract_acs
from src.address_intel.crime_local import fetch_nearby_crime
from src.address_intel.geocoder import geocode_address
from src.address_intel.google_usage import can_fetch_amenities, get_usage, session_cap
from src.address_intel.market_context import (
    fetch_county_fhfa,
    fetch_county_zillow,
    fetch_state_crime_rates,
)
from src.address_intel.permits_local import fetch_county_permit_series, fetch_nearby_permits
from src.address_intel.traffic import fetch_county_traffic, fetch_nearby_traffic
from src.address_intel.weather import fetch_weather, weather_label
from src.address_intel.zoning import fetch_zoning
from src.config import ROOT as CONFIG_ROOT, get_api_key, get_google_maps_api_key
from streamlit_site_selection import render_site_selection_tab

CONFIG_PATH = ROOT / "config" / "dallas.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fmt_number(value, prefix: str = "", suffix: str = "") -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric) or numeric < 0:
        return "—"
    if isinstance(numeric, float) and not numeric.is_integer():
        if numeric >= 1_000_000:
            return f"{prefix}{numeric / 1_000_000:.1f}M{suffix}"
        if numeric >= 10_000:
            return f"{prefix}{numeric:,.0f}{suffix}"
        return f"{prefix}{numeric:,.1f}{suffix}"
    numeric = int(numeric)
    if numeric >= 1_000_000:
        return f"{prefix}{numeric / 1_000_000:.1f}M{suffix}"
    return f"{prefix}{numeric:,}{suffix}"


def fmt_acs_value(key: str, value) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric) or numeric < 0:
        if key == "median_home_value":
            return "N/A (suppressed by Census)"
        return "—"
    if key.endswith("_pct"):
        return fmt_number(value, suffix="%")
    if "income" in key or "value" in key:
        return fmt_number(value, "$")
    return fmt_number(value)


def tract_vs_county_chart(tract: dict, county: dict, county_name: str) -> go.Figure:
    metrics = [
        ("Median Income", "median_household_income", "$"),
        ("Median Home Value", "median_home_value", "$"),
        ("Median Age", "median_age", ""),
    ]
    labels, tract_vals, county_vals = [], [], []
    for label, key, _ in metrics:
        tv, cv = tract.get(key), county.get(key)
        if tv is not None and cv is not None:
            labels.append(label)
            tract_vals.append(tv)
            county_vals.append(cv)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Your Tract", x=labels, y=tract_vals, marker_color="#1565C0"))
    fig.add_trace(go.Bar(name=county_name, x=labels, y=county_vals, marker_color="#90CAF9"))
    fig.update_layout(
        title="Tract vs. County Comparison",
        barmode="group",
        margin={"t": 40, "b": 40, "l": 40, "r": 20},
        height=360,
    )
    return fig


def amenity_score_chart(categories: list[dict]) -> go.Figure:
    if not categories:
        return go.Figure()
    df = pd.DataFrame(categories)
    fig = px.bar(
        df,
        x="score",
        y="label",
        orientation="h",
        color="score",
        color_continuous_scale=["#E3F2FD", "#1565C0"],
        labels={"score": "Score (0–100)", "label": ""},
        title="Amenity Scores by Category",
    )
    fig.update_layout(
        coloraxis_showscale=False,
        yaxis={"categoryorder": "total ascending"},
        height=420,
        margin={"t": 40, "b": 20, "l": 20, "r": 20},
    )
    return fig


def amenity_map(latitude: float, longitude: float, places: list) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=[latitude],
            lon=[longitude],
            mode="markers",
            marker={"size": 14, "color": "#1565C0"},
            name="Address",
        )
    )
    if places:
        lats = [p.latitude for p in places]
        lons = [p.longitude for p in places]
        names = [p.name for p in places]
        fig.add_trace(
            go.Scattermapbox(
                lat=lats,
                lon=lons,
                mode="markers",
                marker={"size": 9, "color": "#43A047"},
                text=names,
                name="Amenities",
            )
        )
    fig.update_layout(
        mapbox={"style": "open-street-map", "center": {"lat": latitude, "lon": longitude}, "zoom": 13},
        margin={"t": 30, "b": 0, "l": 0, "r": 0},
        height=400,
        showlegend=False,
    )
    return fig


def traffic_map(latitude: float, longitude: float, nearby: pd.DataFrame, radius_miles: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=[latitude],
            lon=[longitude],
            mode="markers",
            marker={"size": 14, "color": "#1565C0"},
            name="Property",
        )
    )
    if not nearby.empty:
        max_aadt = nearby["aadt"].max() or 1
        for _, row in nearby.iterrows():
            lats, lons = row.get("lats"), row.get("lons")
            if not isinstance(lats, list) or not lats:
                continue
            intensity = row["aadt"] / max_aadt
            fig.add_trace(
                go.Scattermapbox(
                    lat=lats,
                    lon=lons,
                    mode="lines",
                    line={"width": 3 + 5 * intensity, "color": f"rgba(21, 101, 192, {0.4 + 0.6 * intensity:.2f})"},
                    name=row["route"],
                    hoverinfo="skip",
                )
            )
    fig.update_layout(
        mapbox={"style": "open-street-map", "center": {"lat": latitude, "lon": longitude}, "zoom": 12},
        margin={"t": 30, "b": 0, "l": 0, "r": 0},
        height=380,
        showlegend=False,
    )
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def cached_geocode(address: str, _schema_version: int = 2):
    return geocode_address(address)


def _geo_zip(geo) -> str:
    """ZIP from geocode result; tolerates cached objects from older schema."""
    z = getattr(geo, "zip_code", None)
    if z:
        return str(z)
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", getattr(geo, "matched_address", "") or "")
    return match.group(1) if match else ""


@st.cache_data(ttl=3600, show_spinner=False)
def cached_tract_acs(state_fips: str, county_code: str, tract_code: str):
    return fetch_tract_acs(state_fips, county_code, tract_code)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_county_acs(county_fips: str):
    return fetch_county_acs(county_fips)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_county_traffic(county_code: int):
    return fetch_county_traffic(county_code)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_nearby_traffic(lat: float, lon: float, radius_miles: float):
    return fetch_nearby_traffic(lat, lon, radius_miles)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_weather(lat: float, lon: float):
    return fetch_weather(lat, lon)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_zoning(lat: float, lon: float, layer_url: str):
    return fetch_zoning(lat, lon, layer_url)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_crime(lat: float, lon: float, radius: float, zip_code: str, url: str):
    return fetch_nearby_crime(lat, lon, radius, zip_code=zip_code or None, api_url=url)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_permits(lat: float, lon: float, radius: float, zip_code: str, url: str, _api_version: int = 4):
    return fetch_nearby_permits(lat, lon, radius, zip_code=zip_code or None, api_url=url)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_zillow(county_fips: str):
    return fetch_county_zillow(county_fips)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_fhfa(county_fips: str):
    return fetch_county_fhfa(county_fips)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_state_crime():
    return fetch_state_crime_rates("TX")


@st.cache_data(ttl=86400, show_spinner=False)
def cached_county_permits(county_fips: str):
    return fetch_county_permit_series(county_fips)


@st.cache_data(ttl=604800, show_spinner=False)  # 7 days — repeat addresses don't re-bill
def cached_amenities(
    lat: float,
    lon: float,
    radius: float,
    session_calls_used: int,
    _usage_version: int = 3,
):
    return fetch_amenities(
        round(lat, 3),
        round(lon, 3),
        radius,
        session_calls_used=session_calls_used,
    )


def _load_amenities(lat: float, lon: float, radius: float, enabled: bool) -> dict:
    """Apply session caps and avoid double-counting on Streamlit reruns."""
    if not enabled:
        return {"enabled": False, "categories": [], "overall_score": None, "places": []}

    sess_used = int(st.session_state.get("google_session_calls", 0))
    ok, msg = can_fetch_amenities(sess_used)
    if not ok:
        return {
            "enabled": False,
            "source": "Google Places API (New)",
            "note": msg,
            "categories": [],
            "overall_score": None,
            "places": [],
            "api_calls": 0,
        }

    lookup_key = f"{round(lat, 3)},{round(lon, 3)},{radius}"
    charged: set[str] = st.session_state.setdefault("google_charged_lookups", set())
    already_charged = lookup_key in charged

    result = cached_amenities(lat, lon, radius, sess_used)
    api_calls = int(result.get("api_calls") or 0)
    if api_calls and not already_charged:
        st.session_state["google_session_calls"] = sess_used + api_calls
        charged.add(lookup_key)

    return result


def main() -> None:
    cfg = load_config()
    has_census = bool(get_api_key("CENSUS_API_KEY"))
    has_google = bool(get_google_maps_api_key())
    open_data = cfg.get("open_data", {})

    st.set_page_config(
        page_title="Dallas Location Intelligence",
        page_icon="📍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Dallas–Fort Worth Location Intelligence")
    st.caption(
        "Enter an address to see demographics, home prices, weather, crime, zoning, permits, "
        "traffic, and optional Google amenity scores."
    )

    with st.sidebar:
        st.markdown("**Data sources**")
        st.markdown(
            "- Census Geocoder & ACS 5-Year\n"
            "- Zillow ZHVI & FHFA HPI\n"
            "- Open-Meteo (weather)\n"
            "- Dallas PD & City open data\n"
            "- City of Dallas zoning GIS\n"
            "- FHWA HPMS traffic\n"
            "- Google Places (optional)"
        )
        if has_census:
            st.success("Census API key configured")
        else:
            st.warning("No Census key — demographics may use samples")
        if has_google:
            st.success("Google Maps API key configured")
            usage = get_usage()
            sess_used = int(st.session_state.get("google_session_calls", 0))
            st.caption(
                f"Places API month: **{usage['calls_used']:,}** / **{usage['calls_cap']:,}** "
                f"({usage['calls_remaining']:,} left, hard max {usage['absolute_max']:,})"
            )
            st.caption(
                f"Places API session: **{sess_used:,}** / **{session_cap():,}** calls"
            )
        else:
            st.info(
                "Google amenities off — `GOOGLE_MAPS_API_KEY` not found in `.env` or Streamlit secrets."
            )
            st.caption(f"Add it to `{CONFIG_ROOT / '.env'}` (not `.env.example`), then refresh.")
        use_google = st.toggle(
            "Query Google for nearby amenities",
            value=False,
            disabled=not has_google,
            help=(
                "Off by default to save API quota. Each new address uses up to 3 Nearby Search "
                "calls (~1,500 free addresses/month). Cached 7 days."
            ),
        )
        amenity_radius = st.slider("Amenity search radius (mi)", 0.5, 3.0, 1.0, 0.5)
        crime_radius = st.slider("Crime / permit radius (mi)", 0.5, 2.0, 1.0, 0.25)
        traffic_radius = st.slider("Traffic radius (mi)", 1.0, 10.0, 3.0, 0.5)
        if st.button("Clear cache & refresh", use_container_width=True):
            st.cache_data.clear()
            st.session_state.show_results = True
            st.session_state.site_show_rankings = True
            st.rerun()

    tab_address, tab_site = st.tabs(["Analyze Address", "Find Best Location"])

    with tab_address:
        _render_address_dashboard(
            cfg, has_census, use_google, amenity_radius, crime_radius, traffic_radius, open_data
        )
    with tab_site:
        st.subheader("Find the Best Location")
        metro = cfg.get("metro_name") or str(cfg.get("name", "Dallas–Fort Worth")).split(",")[0].strip()
        st.markdown(
            f"Rank every census tract in the **{metro}** metro by the metrics you care about. "
            "Choose a business preset or set custom weights, then see the top areas on a map."
        )
        render_site_selection_tab(cfg, has_census, show_header=False)


def _render_address_dashboard(
    cfg: dict,
    has_census: bool,
    use_google: bool,
    amenity_radius: float,
    crime_radius: float,
    traffic_radius: float,
    open_data: dict,
) -> None:
    sample = cfg.get("sample_addresses", [])
    default_addr = sample[0] if sample else "1500 Marilla St, Dallas, TX 75201"

    if "address_input" not in st.session_state:
        st.session_state.address_input = default_addr
    if "pending_address" in st.session_state:
        st.session_state.address_input = st.session_state.pop("pending_address")

    c1, c2 = st.columns([4, 1])
    with c1:
        address = st.text_input("Property address", key="address_input")
    with c2:
        st.write("")
        st.write("")
        analyze = st.button("Analyze Address", type="primary", use_container_width=True)

    scols = st.columns(min(len(sample), 4))
    for i, addr in enumerate(sample[:4]):
        with scols[i]:
            if st.button(f"Sample {i + 1}", key=f"sample_{i}", use_container_width=True):
                st.session_state.pending_address = addr
                st.session_state.run_analysis = True
                st.rerun()

    if st.session_state.pop("run_analysis", False):
        analyze = True
        st.session_state.show_results = True
    if analyze:
        st.session_state.show_results = True

    if not st.session_state.get("show_results"):
        st.info("Enter a Dallas-area address and click **Analyze Address**.")
        _show_overview(cfg)
        return

    with st.spinner("Geocoding and fetching data..."):
        try:
            geo = cached_geocode(address)
        except ValueError as exc:
            st.error(str(exc))
            return

        county_code = geo.county_fips[2:]
        hpms_code = int(county_code)  # Dallas County = 113

        tract = cached_tract_acs(geo.state_fips, county_code, geo.tract_code)
        county = cached_county_acs(geo.county_fips)
        traffic_county = cached_county_traffic(hpms_code)
        nearby_traffic = cached_nearby_traffic(geo.latitude, geo.longitude, traffic_radius)
        weather = cached_weather(geo.latitude, geo.longitude)
        zoning = cached_zoning(
            geo.latitude,
            geo.longitude,
            open_data.get(
                "zoning_map_server",
                "https://egis.dallascityhall.com/arcgis/rest/services/Sdc_public/Zoning/MapServer/15",
            ),
        )
        zillow = cached_zillow(geo.county_fips)
        fhfa = cached_fhfa(geo.county_fips)
        state_crime = cached_state_crime()
        county_permits = cached_county_permits(geo.county_fips)
        zip_code = _geo_zip(geo)
        crime = cached_crime(
            geo.latitude,
            geo.longitude,
            crime_radius,
            zip_code,
            open_data.get("crime_incidents_url", ""),
        )
        permits = cached_permits(
            geo.latitude,
            geo.longitude,
            crime_radius,
            zip_code,
            open_data.get("building_permits_url", ""),
        )
        amenities = _load_amenities(geo.latitude, geo.longitude, amenity_radius, use_google)

    # Header
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(geo.matched_address)
        st.markdown(
            f"**{geo.tract_name}** · {geo.county_name} · "
            f"ZIP {zip_code or '—'} · Lat {geo.latitude:.4f}, Lon {geo.longitude:.4f}"
        )
    with col2:
        st.map(pd.DataFrame({"lat": [geo.latitude], "lon": [geo.longitude]}), zoom=13)

    st.divider()

    # Zoning & permits (address-level land use)
    st.subheader("Zoning & Permits")
    z1, z2, z3, z4 = st.columns(4)
    land_cat = zoning.get("land_use_category", "Unknown")
    with z1:
        st.metric("Zoning District", zoning.get("zone_code") or "—")
    with z2:
        st.metric("Allowed Land Use", land_cat)
    with z3:
        zip_label = f"ZIP {zip_code}" if zip_code else "Area"
        st.metric(
            f"Permits ({zip_label})",
            permits.get("permit_count", "—"),
            f"Last ~{max(1, permits.get('lookback_days', 1095) // 365)} yrs",
        )
    with z4:
        st.metric(
            "County Housing Permits (FRED)",
            fmt_number(county_permits.get("building_permits_latest")),
            county_permits.get("building_permits_year"),
        )

    if land_cat == "Unknown":
        st.warning(
            "No Dallas zoning polygon at this point — likely **outside Dallas city limits**. "
            "Zoning data covers the City of Dallas only (not Plano, Irving, Fort Worth, etc.)."
        )
    else:
        st.info(
            f"**{zoning.get('zone_code')}** is classified as **{land_cat}** under City of Dallas base zoning. "
            "This indicates what the city allows on this parcel — not what is currently built."
        )

    if zoning.get("note"):
        st.caption(zoning["note"])
    if permits.get("note"):
        st.caption(permits["note"])
    if permits.get("permit_count", 0) > 0:
        st.warning(
            "Dallas open-data building permits are an **archived snapshot** (mostly 2018–2020). "
            "For current permit activity, the city uses "
            "[DallasNow](https://aca-prod.accela.com/DALLASTX/Default.aspx). "
            "County **FRED** housing permits above reflect recent county-wide trends."
        )

    cat_breakdown = permits.get("category_breakdown") or {}
    if cat_breakdown:
        st.markdown("**Recent permit activity by use type** (same ZIP)")
        cb1, cb2, cb3, cb4 = st.columns(4)
        cols = [cb1, cb2, cb3, cb4]
        for i, (cat, count) in enumerate(cat_breakdown.items()):
            with cols[i % 4]:
                st.metric(cat, count)

    permit_df = permits.get("permits", pd.DataFrame())
    if isinstance(permit_df, pd.DataFrame) and not permit_df.empty:
        with st.expander("Recent building permits in this ZIP"):
            show_cols = [
                c
                for c in (
                    "issued_date",
                    "permit_type",
                    "land_use",
                    "_land_use_category",
                    "street_address",
                    "value",
                    "work_description",
                )
                if c in permit_df.columns
            ]
            st.dataframe(
                permit_df[show_cols].head(25),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # Weather + home prices
    st.subheader("Weather & Home Prices")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.metric("Current Temp", f"{weather.get('temp_f', '—')}°F", weather_label(weather.get("weather_code")))
    with e2:
        st.metric("Today High / Low", f"{fmt_number(weather.get('high_f'))} / {fmt_number(weather.get('low_f'))}°F")
    with e3:
        st.metric("Zillow ZHVI (County)", fmt_number(zillow.get("zillow_zhvi"), "$"), zillow.get("zillow_zhvi_month"))
    with e4:
        st.metric(
            "FHFA HPI (County)",
            fmt_number(fhfa.get("fhfa_hpi_index")),
            f"Year {fhfa.get('fhfa_hpi_year')}" if fhfa.get("fhfa_hpi_year") else fhfa.get("note"),
        )

    st.divider()

    # Demographics
    st.subheader("Demographics (Census ACS)")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Population (Tract)", fmt_number(tract.get("population")))
    with m2:
        st.metric("Median Income", fmt_number(tract.get("median_household_income"), "$"))
    with m3:
        st.metric("Median Home Value (Tract)", fmt_acs_value("median_home_value", tract.get("median_home_value")))
    with m4:
        st.metric("Median Age", fmt_number(tract.get("median_age"), suffix=" yrs"))
    with m5:
        st.metric("College Degree+", fmt_number(tract.get("college_plus_pct"), suffix="%"))

    st.plotly_chart(
        tract_vs_county_chart(tract, county, geo.county_name),
        use_container_width=True,
    )

    st.divider()

    # Crime
    st.subheader("Safety")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric(
            f"PD Incidents ({crime_radius:g} mi)",
            crime.get("incident_count", "—"),
            f"Last {crime.get('lookback_days', 365)} days",
        )
    with s2:
        st.metric("Violent (nearby)", crime.get("violent_count", "—"))
    with s3:
        st.metric("Property (nearby)", crime.get("property_count", "—"))
    with s4:
        st.metric(
            "TX Violent Crime Rate",
            fmt_number(state_crime.get("violent_crime_rate")),
            "State proxy / 100K",
        )
    st.caption(f"Crime: {crime.get('source')} — {crime.get('note', '')}")
    if crime.get("top_offense_types"):
        with st.expander("Top nearby offense types"):
            st.json(crime["top_offense_types"])

    st.divider()

    # Amenities
    st.subheader("Nearby Amenities")
    if amenities.get("enabled"):
        a1, a2 = st.columns([1, 2])
        with a1:
            st.metric("Overall Amenity Score", f"{amenities.get('overall_score', '—')}/100")
            st.caption(
                "Score averages 10 categories (grocery, pharmacy, gym, convenience, "
                "restaurant, school, hospital, park, bank, shopping). "
                "Google returns **GPS coordinates** for each place — not a built-in score."
            )
            cat_df = pd.DataFrame(amenities["categories"])[
                ["label", "count", "nearest_mi", "score"]
            ].rename(
                columns={
                    "label": "Category",
                    "count": "Count",
                    "nearest_mi": "Nearest (mi)",
                    "score": "Score",
                }
            )
            st.dataframe(cat_df, use_container_width=True, hide_index=True)
        with a2:
            st.plotly_chart(amenity_score_chart(amenities["categories"]), use_container_width=True)
        st.plotly_chart(
            amenity_map(geo.latitude, geo.longitude, amenities.get("places") or []),
            use_container_width=True,
        )
        with st.expander("Amenity places (with coordinates)"):
            rows = [
                {
                    "Name": p.name,
                    "Type": p.place_type,
                    "Distance (mi)": p.distance_mi,
                    "Latitude": p.latitude,
                    "Longitude": p.longitude,
                    "Rating": p.rating,
                }
                for p in amenities.get("places") or []
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(
            amenities.get("note")
            or "Enable **Query Google for nearby amenities** in the sidebar (requires GOOGLE_MAPS_API_KEY)."
        )
        st.markdown("**Categories scored when enabled:** " + ", ".join(label for _, label in AMENITY_CATEGORIES))

    st.divider()

    # Traffic
    st.subheader("Traffic & Mobility")
    t1, t2, t3 = st.columns(3)
    with t1:
        st.metric("County Mean AADT", fmt_number(traffic_county.get("mean_aadt")))
    with t2:
        st.metric("County Peak AADT", fmt_number(traffic_county.get("max_aadt")))
    with t3:
        st.metric("Long Commute (Tract)", fmt_number(tract.get("commute_60_plus_pct"), suffix="%"))

    st.plotly_chart(
        traffic_map(geo.latitude, geo.longitude, nearby_traffic, traffic_radius),
        use_container_width=True,
    )

    with st.expander("Raw data tables"):
        st.markdown("**Tract ACS**")
        st.dataframe(pd.DataFrame([tract]).T.rename(columns={0: "Value"}))
        st.markdown("**County home price context**")
        st.json({"zillow": zillow, "fhfa": fhfa, "fred_permits": county_permits, "state_crime": state_crime})
        if not crime.get("incidents", pd.DataFrame()).empty:
            st.markdown("**Nearby PD incidents (sample)**")
            show_crime = crime["incidents"].drop(
                columns=["geocoded_column"], errors="ignore"
            ).head(50)
            st.dataframe(show_crime, use_container_width=True, hide_index=True)


def _show_overview(cfg: dict) -> None:
    st.subheader("What this dashboard shows")
    st.markdown(
        f"""
        Scoped to **{cfg['name']}** ({cfg['county_name']}). Enter any address in the DFW metro:

        1. **Weather** — current conditions via Open-Meteo (free)
        2. **Zoning** — City of Dallas base zoning district (commercial / residential / industrial)
        3. **Home prices** — Zillow ZHVI and FHFA HPI at county level; Census tract values where available
        4. **Crime** — Dallas PD incidents near the address + Texas FBI state rates
        5. **Permits** — nearby Dallas building permits + FRED county permit series
        6. **Demographics** — Census ACS tract income, age, education
        7. **Amenities** (optional) — Google Places with lat/lon and a composite amenity score
        8. **Traffic** — FHWA daily vehicle counts on nearby roads
        """
    )


if __name__ == "__main__":
    main()
