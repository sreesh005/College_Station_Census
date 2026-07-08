-- Location intelligence schema (mirrors SQLite output)
-- Connect Power BI Desktop: Get Data -> SQLite -> data/location_intelligence.db

CREATE VIEW IF NOT EXISTS vw_county_dashboard AS
SELECT
    d.county_label,
    d.county_role,
    f.county_fips,
    f.population,
    f.median_household_income,
    f.households,
    f.median_home_value,
    f.building_permits_latest,
    f.building_permits_year,
    f.permits_per_1k_households,
    f.total_establishments,
    f.retail_establishments,
    f.retail_employment,
    f.retail_establishments_per_10k_pop,
    f.mean_aadt,
    f.max_aadt,
    f.p90_aadt,
    f.violent_crime_per_100k,
    f.property_crime_per_100k,
    f.general_location_score,
    f.score_population,
    f.score_income,
    f.score_growth,
    f.score_traffic,
    f.score_retail_density,
    f.score_crime
FROM fact_county_features f
JOIN dim_county d ON f.county_fips = d.county_fips
ORDER BY f.general_location_score DESC;
