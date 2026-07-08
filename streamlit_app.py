"""College Station address intelligence demo — Streamlit app."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.address_intel.census import fetch_county_acs, fetch_tract_acs
from src.address_intel.geocoder import geocode_address
from src.address_intel.traffic import fetch_county_traffic, fetch_nearby_traffic
from src.config import get_api_key

CONFIG_PATH = ROOT / "config" / "college_station.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fmt_number(value, prefix: str = "", suffix: str = "") -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return "—"
    if numeric < 0:
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


def metric_card(label: str, value: str, help_text: str = "") -> None:
    st.metric(label, value, help=help_text or None)


def housing_chart(tract: dict) -> go.Figure:
    owner = tract.get("owner_occupied") or 0
    renter = tract.get("renter_occupied") or 0
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Owner-Occupied", "Renter-Occupied"],
                values=[owner, renter],
                hole=0.45,
                marker={"colors": ["#500000", "#C4A882"]},
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(
        title="Housing Tenure (Tract)",
        showlegend=False,
        margin={"t": 40, "b": 20, "l": 20, "r": 20},
        height=320,
    )
    return fig


def education_chart(tract: dict) -> go.Figure:
    bachelors = tract.get("bachelors_degree") or 0
    masters = tract.get("masters_degree") or 0
    universe = tract.get("education_universe") or 0
    other = max(universe - bachelors - masters, 0)
    fig = go.Figure(
        data=[
            go.Bar(
                x=["Bachelor's", "Master's+", "Other"],
                y=[bachelors, masters, other],
                marker_color=["#500000", "#732F2F", "#D4C4B0"],
            )
        ]
    )
    fig.update_layout(
        title="Education (Population 25+, Tract)",
        yaxis_title="People",
        margin={"t": 40, "b": 40, "l": 40, "r": 20},
        height=320,
    )
    return fig


def traffic_chart(nearby: pd.DataFrame, radius_miles: float) -> go.Figure:
    fig = px.bar(
        nearby.head(10),
        x="aadt",
        y="route",
        orientation="h",
        color="aadt",
        color_continuous_scale=["#D4C4B0", "#500000"],
        labels={"aadt": "Daily Vehicles (AADT)", "route": "Road Segment"},
    )
    fig.update_layout(
        title=f"Nearest High-Traffic Roads ({radius_miles:g} mi radius)",
        coloraxis_showscale=False,
        margin={"t": 40, "b": 40, "l": 20, "r": 20},
        height=380,
        yaxis={"categoryorder": "total ascending"},
    )
    return fig


def traffic_map(
    latitude: float,
    longitude: float,
    nearby: pd.DataFrame,
    radius_miles: float,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattermapbox(
            lat=[latitude],
            lon=[longitude],
            mode="markers",
            marker={"size": 14, "color": "#500000"},
            name="Property",
            text=["Your address"],
        )
    )

    if nearby.empty:
        fig.update_layout(title="No traffic segments found")
        return fig

    max_aadt = nearby["aadt"].max() or 1
    for _, row in nearby.iterrows():
        lats = row.get("lats")
        lons = row.get("lons")
        if not isinstance(lats, list) or not isinstance(lons, list) or not lats:
            continue
        intensity = row["aadt"] / max_aadt
        color = f"rgba(80, 0, 0, {0.35 + 0.65 * intensity:.2f})"
        fig.add_trace(
            go.Scattermapbox(
                lat=lats,
                lon=lons,
                mode="lines",
                line={"width": 4 + 6 * intensity, "color": color},
                name=row["route"],
                text=[f"{row['route']}<br>AADT: {row['aadt']:,}"],
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=f"Traffic Map ({radius_miles:g} mi search radius)",
        mapbox={
            "style": "open-street-map",
            "center": {"lat": latitude, "lon": longitude},
            "zoom": 12 if radius_miles <= 3 else 11,
        },
        margin={"t": 40, "b": 0, "l": 0, "r": 0},
        height=420,
        showlegend=False,
    )
    return fig


def tract_vs_county_chart(tract: dict, county: dict) -> go.Figure:
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
    fig.add_trace(go.Bar(name="Your Tract", x=labels, y=tract_vals, marker_color="#500000"))
    fig.add_trace(go.Bar(name="Brazos County", x=labels, y=county_vals, marker_color="#C4A882"))
    fig.update_layout(
        title="Tract vs. County Comparison",
        barmode="group",
        yaxis_title="Value ($)",
        margin={"t": 40, "b": 40, "l": 40, "r": 20},
        height=360,
    )
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def cached_geocode(address: str):
    return geocode_address(address)


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


def main() -> None:
    cfg = load_config()
    has_census_key = bool(get_api_key("CENSUS_API_KEY"))

    st.set_page_config(
        page_title="College Station Location Intel",
        page_icon="📍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("College Station Location Intelligence")
    st.caption(
        "Enter a property address to see census demographics, housing, education, "
        "and nearby traffic — a preview of what we can build for real estate agents."
    )

    with st.sidebar:
        st.header("Search")
        sample = cfg.get("sample_addresses", [])
        default_addr = sample[0] if sample else "400 Bizzell St, College Station, TX 77843"

        if "address_input" not in st.session_state:
            st.session_state.address_input = default_addr

        if "pending_address" in st.session_state:
            st.session_state.address_input = st.session_state.pop("pending_address")

        address = st.text_input("Property address", key="address_input")
        traffic_radius = st.slider(
            "Traffic search radius (miles)", 1.0, 10.0, 3.0, 0.5, key="traffic_radius"
        )

        analyze = st.button("Analyze Address", type="primary", use_container_width=True)

        st.divider()
        st.subheader("Try a sample")
        for i, addr in enumerate(sample):
            if st.button(addr, key=f"sample_{i}", use_container_width=True):
                st.session_state.pending_address = addr
                st.session_state.run_analysis = True
                st.rerun()

        if st.session_state.pop("run_analysis", False):
            analyze = True
            st.session_state.show_results = True

        if analyze:
            st.session_state.show_results = True

        if st.button("Clear cache & refresh data", use_container_width=True):
            st.cache_data.clear()
            st.session_state.show_results = True
            st.rerun()

        st.divider()
        st.markdown("**Data sources**")
        st.markdown(
            "- Census Geocoder (address → tract)\n"
            "- ACS 5-Year Estimates\n"
            "- FHWA HPMS (road traffic)"
        )
        if has_census_key:
            st.success("Census API key configured")
        else:
            st.warning("No Census API key — using sample demographics")

    if not st.session_state.get("show_results"):
        st.info("Enter an address and click **Analyze Address** to get started.")
        _show_overview(cfg)
        return

    with st.spinner("Geocoding address and fetching data..."):
        try:
            geo = cached_geocode(address)
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Geocoding failed: {exc}")
            return

        county_code = geo.county_fips[2:]
        tract = cached_tract_acs(geo.state_fips, county_code, geo.tract_code)
        county = cached_county_acs(geo.county_fips)
        traffic_county = cached_county_traffic(cfg["county_code"])
        nearby_traffic = cached_nearby_traffic(geo.latitude, geo.longitude, traffic_radius)

    # Location header
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(geo.matched_address)
        st.markdown(
            f"**{geo.tract_name}** · {geo.county_name} · "
            f"Lat {geo.latitude:.4f}, Lon {geo.longitude:.4f}"
        )
    with col2:
        map_df = pd.DataFrame({"lat": [geo.latitude], "lon": [geo.longitude]})
        st.map(map_df, zoom=13)

    st.divider()

    # Key metrics
    st.subheader("Key Demographics")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Population (Tract)", fmt_number(tract.get("population")))
    with m2:
        metric_card("Median Income (Tract)", fmt_number(tract.get("median_household_income"), "$"))
    with m3:
        tract_home = tract.get("median_home_value")
        home_numeric = pd.to_numeric(tract_home, errors="coerce")
        if pd.isna(home_numeric) or home_numeric < 0:
            county_home = county.get("median_home_value")
            fallback = f" (county: {fmt_number(county_home, '$')})" if county_home else ""
            metric_card(
                "Median Home Value (Tract)",
                "N/A",
                "Census does not publish tract-level home values when there are too few "
                f"owner-occupied units — common in student housing areas.{fallback}",
            )
        else:
            metric_card("Median Home Value (Tract)", fmt_number(tract_home, "$"))
    with m4:
        metric_card("Median Age (Tract)", fmt_number(tract.get("median_age"), suffix=" yrs"))
    with m5:
        metric_card(
            "College Degree+ (Tract)",
            fmt_number(tract.get("college_plus_pct"), suffix="%"),
            "Share of population 25+ with bachelor's or higher",
        )

    st.divider()

    # Charts row 1
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(housing_chart(tract), use_container_width=True)
    with c2:
        st.plotly_chart(education_chart(tract), use_container_width=True)
    with c3:
        st.plotly_chart(tract_vs_county_chart(tract, county), use_container_width=True)

    st.divider()

    # Traffic section
    st.subheader("Traffic & Mobility")
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        metric_card(
            "County Mean AADT",
            fmt_number(traffic_county.get("mean_aadt")),
            "Average daily traffic across Brazos County road segments",
        )
    with t2:
        metric_card("County Peak AADT", fmt_number(traffic_county.get("max_aadt")))
    with t3:
        metric_card("90th Percentile AADT", fmt_number(traffic_county.get("p90_aadt")))
    with t4:
        metric_card(
            "Long Commute (Tract)",
            fmt_number(tract.get("commute_60_plus_pct"), suffix="%"),
            "Workers with 60+ minute commute",
        )

    st.plotly_chart(
        traffic_map(geo.latitude, geo.longitude, nearby_traffic, traffic_radius),
        use_container_width=True,
    )
    st.plotly_chart(traffic_chart(nearby_traffic, traffic_radius), use_container_width=True)
    st.caption(
        f"Showing {len(nearby_traffic)} road segments within **{traffic_radius:g} miles** "
        "of the property. Adjust the radius slider to update."
    )

    st.divider()

    # Detail tables
    with st.expander("Tract detail (ACS)"):
        tract_display = {
            k: fmt_acs_value(k, v) for k, v in tract.items() if not k.startswith("_")
        }
        st.dataframe(
            pd.DataFrame([tract_display]).T.rename(columns={0: "Value"}),
            use_container_width=True,
        )
        st.caption(f"Source: {tract.get('source', 'unknown')} · Vintage: {tract.get('acs_vintage', '—')}")

    with st.expander("County context (Brazos County)"):
        county_display = {
            k: fmt_acs_value(k, v) for k, v in county.items() if not k.startswith("_")
        }
        st.dataframe(
            pd.DataFrame([county_display]).T.rename(columns={0: "Value"}),
            use_container_width=True,
        )

    with st.expander("Nearby road segments"):
        display_traffic = nearby_traffic.drop(columns=["lats", "lons"], errors="ignore")
        st.dataframe(display_traffic, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "**What's next?** This demo shows tract-level census demographics and nearby traffic. "
        "Future versions could add school ratings, flood zones, crime stats, walkability scores, "
        "and comparable sales — tell us what matters most for your agents."
    )


def _show_overview(cfg: dict) -> None:
    st.subheader("What this tool does")
    st.markdown(
        """
        This is a **proof-of-concept** for wrapping public data around a property address.
        A real estate agent types an address and instantly sees:

        1. **Geographic context** — matched address, census tract, map pin
        2. **Demographics** — population, income, home values, age, education
        3. **Housing mix** — owner vs. renter occupancy in the surrounding tract
        4. **Traffic exposure** — daily vehicle counts on nearby roads (FHWA data)
        5. **County comparison** — how the tract compares to Brazos County overall
        """
    )

    st.subheader("College Station focus")
    st.markdown(
        f"""
        This pilot is scoped to **{cfg['name']}** ({cfg['county_name']}, FIPS {cfg['county_fips']}).
        The underlying pipeline already works for DFW counties — the same pattern extends to
        any market with public census and transportation data.
        """
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Census data (ACS 5-Year)**")
        st.markdown(
            "- Population & median age\n"
            "- Household income & home values\n"
            "- Housing tenure (owner/renter)\n"
            "- Education attainment\n"
            "- Commute patterns"
        )
    with c2:
        st.markdown("**Traffic data (FHWA HPMS)**")
        st.markdown(
            "- Annual average daily traffic (AADT)\n"
            "- Nearest high-traffic road segments\n"
            "- County-level traffic summary\n"
            "- Road functional classification"
        )


if __name__ == "__main__":
    main()
