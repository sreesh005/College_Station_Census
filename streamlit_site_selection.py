"""Site selection tab — weighted tract ranking (config-driven county)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.site_selection.presets import BUSINESS_PRESETS, METRIC_KEYS, METRIC_LABELS
from src.site_selection.scorecard import build_tract_scorecard
from src.site_selection.scoring import rank_tracts


@st.cache_data(ttl=3600, show_spinner=False)
def cached_tract_scorecard(state_fips: str, county_code: str, traffic_radius: float) -> pd.DataFrame:
    return build_tract_scorecard(
        state_fips,
        county_code,
        traffic_radius_miles=traffic_radius,
    )


def _metro_label(cfg: dict) -> str:
    """User-facing metro name for site selection copy."""
    if cfg.get("metro_name"):
        return str(cfg["metro_name"])
    name = str(cfg.get("name", "Dallas–Fort Worth"))
    return name.split(",")[0].strip()


def site_selection_map(ranked: pd.DataFrame, metro_label: str) -> go.Figure:
    fig = px.scatter_mapbox(
        ranked,
        lat="latitude",
        lon="longitude",
        color="site_score",
        size="population",
        hover_name="tract_label",
        hover_data={
            "site_score": True,
            "median_household_income": ":,.0f",
            "nearby_max_aadt": ":,.0f",
            "pct_2plus_vehicles": ":.1f",
            "college_plus_pct": ":.1f",
            "latitude": False,
            "longitude": False,
            "population": ":,.0f",
        },
        color_continuous_scale=["#E3F2FD", "#1565C0"],
        size_max=18,
        zoom=10,
        title=f"Site Selection Score Map ({metro_label})",
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"t": 40, "b": 0, "l": 0, "r": 0},
        height=520,
    )
    return fig


def _apply_preset_weights(preset: str) -> None:
    if st.session_state.get("last_preset") == preset:
        return
    for key in METRIC_KEYS:
        st.session_state[f"weight_{key}"] = int(BUSINESS_PRESETS[preset][key] * 100)
    st.session_state.last_preset = preset


def render_site_selection_tab(cfg: dict, has_census_key: bool, show_header: bool = True) -> None:
    metro = _metro_label(cfg)
    county_name = cfg.get("county_name", "Dallas County")
    if show_header:
        st.subheader("Find the Best Location")
        st.markdown(
            f"Rank every census tract in the **{metro}** metro by the metrics you care about. "
            "Choose a business preset or set custom weights, then see the top areas on a map."
        )
    st.caption(f"Tract scorecard scope: {county_name} (DFW pilot county).")

    if not has_census_key:
        st.error(
            "Site selection requires a Census API key. "
            "Locally: add `CENSUS_API_KEY` to `.env`. "
            "On Streamlit Cloud: add it under **App settings → Secrets**."
        )
        return

    col_preset, col_traffic = st.columns([2, 1])
    with col_preset:
        preset = st.selectbox(
            "Business type preset",
            list(BUSINESS_PRESETS.keys()),
            key="site_preset",
        )
        _apply_preset_weights(preset)
        st.caption(str(BUSINESS_PRESETS[preset]["description"]))
    with col_traffic:
        traffic_radius = st.slider(
            "Traffic sample radius (mi)",
            0.5,
            3.0,
            1.5,
            0.5,
            key="site_traffic_radius",
            help="Used to estimate peak nearby AADT at each tract centroid.",
        )

    st.markdown("**Metric priorities** (weights auto-normalize to 100%)")
    weight_cols = st.columns(len(METRIC_KEYS))
    weights: dict[str, float] = {}
    for col, key in zip(weight_cols, METRIC_KEYS):
        with col:
            pct = st.slider(
                METRIC_LABELS[key],
                0,
                100,
                st.session_state.get(f"weight_{key}", int(BUSINESS_PRESETS[preset][key] * 100)),
                5,
                key=f"weight_{key}",
            )
            weights[key] = pct / 100

    rank_clicked = st.button("Rank Locations", type="primary", key="rank_locations")

    if rank_clicked:
        st.session_state.site_show_rankings = True

    if not st.session_state.get("site_show_rankings"):
        st.info("Choose your priorities and click **Rank Locations**. First run may take 1–2 minutes.")
        st.markdown(
            "**Metrics scored per tract:**\n"
            "- Market size (population)\n"
            "- Median household income\n"
            "- Peak nearby traffic (FHWA AADT)\n"
            "- Households with 2+ vehicles\n"
            "- College-educated population share"
        )
        return

    try:
        with st.spinner(f"Building tract scorecard for {metro} (cached after first run)..."):
            scorecard = cached_tract_scorecard(
                cfg["state_fips"],
                cfg["county_fips"][2:],
                traffic_radius,
            )
        ranked = rank_tracts(scorecard, weights)
    except RuntimeError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Site selection failed: {exc}")
        return

    top = ranked.head(10)
    st.success(f"Ranked **{len(ranked)}** tracts in **{metro}** ({county_name}).")

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Top Tract Score", f"{top.iloc[0]['site_score']:.1f}")
    with m2:
        st.metric("#1 Tract", top.iloc[0]["tract_label"])
    with m3:
        st.metric("Top Traffic (AADT)", f"{top.iloc[0]['nearby_max_aadt']:,.0f}")

    st.plotly_chart(site_selection_map(ranked, metro), use_container_width=True)

    st.subheader("Top 10 Tracts")
    top_display = top.copy()
    top_display["Coordinates"] = top_display.apply(
        lambda r: f"{r['latitude']:.4f}, {r['longitude']:.4f}", axis=1
    )
    display = top_display[
        [
            "site_score",
            "tract_label",
            "tract_fips",
            "Coordinates",
            "population",
            "median_household_income",
            "nearby_max_aadt",
            "pct_2plus_vehicles",
            "college_plus_pct",
        ]
    ].rename(
        columns={
            "site_score": "Score",
            "tract_label": "Census Tract",
            "tract_fips": "Tract FIPS",
            "population": "Population",
            "median_household_income": "Median Income",
            "nearby_max_aadt": "Peak Traffic (AADT)",
            "pct_2plus_vehicles": "2+ Vehicles %",
            "college_plus_pct": "College %",
        }
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.1f"),
            "Population": st.column_config.NumberColumn(format="%d"),
            "Median Income": st.column_config.NumberColumn(format="$%d"),
            "Peak Traffic (AADT)": st.column_config.NumberColumn(format="%d"),
            "2+ Vehicles %": st.column_config.NumberColumn(format="%.1f%%"),
            "College %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    with st.expander("Full tract rankings (includes latitude & longitude)"):
        st.dataframe(ranked, use_container_width=True, hide_index=True)
