from __future__ import annotations

import pandas as pd

from .presets import METRIC_KEYS

RAW_METRIC_COLUMNS = {
    "population": "population",
    "income": "median_household_income",
    "traffic": "nearby_max_aadt",
    "vehicle_ownership": "pct_2plus_vehicles",
    "education": "college_plus_pct",
}


def _min_max_scale(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty or valid.min() == valid.max():
        return pd.Series([50.0] * len(series), index=series.index)
    return ((numeric - valid.min()) / (valid.max() - valid.min()) * 100).round(1)


def rank_tracts(scorecard: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Apply weights and return tracts sorted by composite site score."""
    df = scorecard.copy()
    normalized_weights = _normalize_weights(weights)

    for metric, column in RAW_METRIC_COLUMNS.items():
        df[f"score_{metric}"] = _min_max_scale(df[column])

    score_cols = [f"score_{m}" for m in METRIC_KEYS]
    weight_vec = [normalized_weights[m] for m in METRIC_KEYS]
    df["site_score"] = sum(df[col] * w for col, w in zip(score_cols, weight_vec)).round(1)

    rank_cols = [
        "site_score",
        "tract_label",
        "tract_fips",
        "latitude",
        "longitude",
        "population",
        "median_household_income",
        "nearby_max_aadt",
        "pct_2plus_vehicles",
        "college_plus_pct",
        *score_cols,
    ]
    existing = [c for c in rank_cols if c in df.columns]
    return df[existing].sort_values("site_score", ascending=False).reset_index(drop=True)


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    filtered = {k: max(float(weights.get(k, 0)), 0) for k in METRIC_KEYS}
    total = sum(filtered.values())
    if total <= 0:
        even = 1 / len(METRIC_KEYS)
        return {k: even for k in METRIC_KEYS}
    return {k: v / total for k, v in filtered.items()}
