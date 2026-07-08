from __future__ import annotations

import pandas as pd

from .config import PROCESSED_DIR, RAW_DIR, load_pilot_config


def _read_csv(name: str) -> pd.DataFrame | None:
    path = RAW_DIR / name
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype={"county_fips": str})
    df["county_fips"] = df["county_fips"].str.zfill(5)
    return df


def _min_max_scale(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if valid.empty or valid.min() == valid.max():
        return pd.Series([50.0] * len(series), index=series.index)
    return (series - valid.min()) / (valid.max() - valid.min()) * 100


def stitch_county_features() -> pd.DataFrame:
    cfg = load_pilot_config()
    meta = pd.DataFrame(cfg["counties"])
    meta = meta.rename(columns={"fips": "county_fips", "name": "county_label", "role": "county_role"})
    meta["county_fips"] = meta["county_fips"].astype(str).str.zfill(5)

    required = {
        "acs_county.csv": "ACS demographics",
        "building_permits.csv": "FRED permits",
        "cbp_county.csv": "CBP",
        "crime_state_proxy.csv": "Crime",
        "traffic_county.csv": "Traffic",
    }
    for name, label in required.items():
        if _read_csv(name) is None:
            raise FileNotFoundError(f"Missing raw file for {label}: data/raw/{name}")

    acs = _read_csv("acs_county.csv")
    permits = _read_csv("building_permits.csv")
    cbp = _read_csv("cbp_county.csv")
    crime = _read_csv("crime_state_proxy.csv")
    traffic = _read_csv("traffic_county.csv")

    df = meta.merge(acs, on="county_fips", how="left")
    df = df.merge(permits, on="county_fips", how="left")
    df = df.merge(cbp, on="county_fips", how="left")
    df = df.merge(crime, on="county_fips", how="left")
    df = df.merge(traffic, on="county_fips", how="left")

    for optional in (
        "pep_county.csv",
        "fhfa_hpi.csv",
        "zillow_zhvi.csv",
        "ntad_traffic.csv",
        "blm_leases.csv",
        "rrc_wells.csv",
    ):
        extra = _read_csv(optional)
        if extra is not None:
            extra = extra.drop(columns=[c for c in extra.columns if c == "note"], errors="ignore")
            df = df.merge(extra, on="county_fips", how="left")

    df["state_fips"] = cfg["state_fips"]
    df["state_abbr"] = cfg["state_abbr"]
    df["pilot_name"] = cfg["pilot_name"]

    if "violent_crime_rate" in df.columns:
        df["violent_crime_per_100k"] = df["violent_crime_rate"]
        df["property_crime_per_100k"] = df["property_crime_rate"]
        df["burglary_per_100k"] = df["burglary_rate"]
        df["larceny_per_100k"] = df["larceny_rate"]
    else:
        for offense in ("violent_crime", "property_crime", "burglary", "larceny"):
            df[f"{offense}_per_100k"] = (df[offense] / df["population"]) * 100_000

    df["permits_per_1k_households"] = (df["building_permits_latest"] / df["households"]) * 1000
    df["retail_establishments_per_10k_pop"] = (df["retail_establishments"] / df["population"]) * 10_000

    df["score_population"] = _min_max_scale(df["population"])
    df["score_income"] = _min_max_scale(df["median_household_income"])
    df["score_growth"] = _min_max_scale(df["building_permits_latest"])
    df["score_traffic"] = _min_max_scale(df["mean_aadt"])
    df["score_retail_density"] = _min_max_scale(df["retail_establishments_per_10k_pop"])
    df["score_crime"] = 100 - _min_max_scale(df["violent_crime_per_100k"])

    df["general_location_score"] = (
        df["score_population"] * 0.2
        + df["score_income"] * 0.2
        + df["score_growth"] * 0.15
        + df["score_traffic"] * 0.2
        + df["score_retail_density"] * 0.15
        + df["score_crime"] * 0.1
    ).round(1)

    df = df.sort_values("general_location_score", ascending=False)
    out_path = PROCESSED_DIR / "county_features.csv"
    df.to_csv(out_path, index=False)
    return df


if __name__ == "__main__":
    result = stitch_county_features()
    cols = [
        "county_label",
        "population",
        "median_household_income",
        "building_permits_latest",
        "mean_aadt",
        "general_location_score",
    ]
    print(result[cols].to_string(index=False))
