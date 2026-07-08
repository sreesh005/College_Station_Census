from __future__ import annotations

METRIC_LABELS = {
    "population": "Market Size (Population)",
    "income": "Household Income",
    "traffic": "Traffic Exposure",
    "vehicle_ownership": "Vehicle Ownership",
    "education": "Education Level",
}

# Weights must sum to 1.0
BUSINESS_PRESETS: dict[str, dict[str, float | str]] = {
    "Custom": {
        "description": "Set your own priorities with the sliders below.",
        "population": 0.20,
        "income": 0.20,
        "traffic": 0.20,
        "vehicle_ownership": 0.20,
        "education": 0.20,
    },
    "Car Wash": {
        "description": "High traffic visibility, many multi-car households, decent income.",
        "population": 0.15,
        "income": 0.15,
        "traffic": 0.35,
        "vehicle_ownership": 0.30,
        "education": 0.05,
    },
    "Retail Store": {
        "description": "Strong market size and income, good traffic, moderate vehicle access.",
        "population": 0.25,
        "income": 0.30,
        "traffic": 0.25,
        "vehicle_ownership": 0.15,
        "education": 0.05,
    },
    "Coffee Shop / Cafe": {
        "description": "Dense population, higher income and education, walkable traffic corridors.",
        "population": 0.30,
        "income": 0.25,
        "traffic": 0.20,
        "vehicle_ownership": 0.05,
        "education": 0.20,
    },
    "Daycare / Childcare": {
        "description": "Family-oriented areas with income stability and moderate traffic.",
        "population": 0.30,
        "income": 0.30,
        "traffic": 0.10,
        "vehicle_ownership": 0.20,
        "education": 0.10,
    },
    "Warehouse / Logistics": {
        "description": "Highway access and traffic matter most; income/education less important.",
        "population": 0.10,
        "income": 0.10,
        "traffic": 0.50,
        "vehicle_ownership": 0.25,
        "education": 0.05,
    },
}

METRIC_KEYS = list(METRIC_LABELS.keys())
