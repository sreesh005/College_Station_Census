"""Generate the Location Intelligence Data Availability Report (PDF)."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Data_Availability_Report.pdf"


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Location Intelligence - Public Data Availability Assessment", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 20, 20)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def sub_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 4.5, text)
        self.ln(1)

    def mono_block(self, text: str) -> None:
        self.set_font("Courier", "", 7.5)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(0, 3.8, text, fill=True)
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int]) -> None:
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(230, 236, 245)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 7.5)
        fill = False
        for row in rows:
            max_lines = 1
            wrapped = []
            for i, cell in enumerate(row):
                lines = self.multi_cell(col_widths[i], 4, cell, dry_run=True, output="LINES")
                wrapped.append(lines)
                max_lines = max(max_lines, len(lines))
            row_h = max_lines * 4
            if self.get_y() + row_h > 270:
                self.add_page()
            x0, y0 = self.get_x(), self.get_y()
            x = x0
            for i, lines in enumerate(wrapped):
                self.set_xy(x, y0)
                self.multi_cell(col_widths[i], 4, "\n".join(lines), border=1, fill=fill)
                x += col_widths[i]
            self.set_xy(x0, y0 + row_h)
            fill = not fill
        self.ln(2)


def build_report() -> None:
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    # Title page content
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Public Data Availability Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Location Intelligence - Exploratory Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.body(
        "Prepared for: DFW pilot / general site-selection use cases\n"
        "Date: July 6, 2026 (updated with live pilot test results)\n"
        "Scope: Nine public sources requested for DFW pilot counties (Collin, Dallas, Denton, Rockwall, Tarrant)\n"
        "Purpose: Confirm what public data exists, API access, cost, granularity, and what actually worked in production pulls."
    )

    pdf.section_title("Executive Summary")
    pdf.body(
        "A live pilot test on July 6, 2026 confirmed that 8 of 9 requested sources deliver usable data into the "
        "pipeline automatically. Only Texas RRC is partial: the public MFT catalog lists per-county API DBF files, "
        "but programmatic download requires a browser session (GoDrive/PrimeFaces). Three free API keys power the "
        "keyed sources: Census (ACS, PEP, CBP), FRED (building permits), and data.gov (FBI CDE crime). The remaining "
        "six sources require no API key - they use public CSV/XLSX downloads or open ArcGIS/Socrata REST endpoints."
    )

    pdf.section_title("Pilot Live Test Results (July 6, 2026)")
    pdf.sub_title("Connectivity probe: 9/9 OK")
    pdf.table(
        ["Source", "API key?", "Pilot status", "Access method"],
        [
            ["Census ACS (acs/acs5)", "CENSUS_API_KEY", "WORKING", "api.census.gov REST"],
            ["Census PEP (pep/charv)", "CENSUS_API_KEY", "WORKING", "api.census.gov REST"],
            ["FRED building permits", "FRED_API_KEY", "WORKING", "fred.stlouisfed.org REST"],
            ["FBI CDE crime", "DATA_GOV_API_KEY", "WORKING", "api.usa.gov/crime/fbi/cde/..."],
            ["FHFA HPI", "None", "WORKING", "fhfa.gov annual county XLSX download"],
            ["Zillow ZHVI", "None", "WORKING", "zillowstatic.com public CSV download"],
            ["FHWA HPMS traffic", "None", "WORKING", "geo.dot.gov ArcGIS REST (county_code)"],
            ["BTS NTAD", "None", "WORKING", "data.transportation.gov Socrata 8j5p-a5aj"],
            ["BLM MLRS leases", "None", "WORKING", "gis.blm.gov ArcGIS spatial query"],
            ["Texas RRC wells", "None", "PARTIAL", "mft.rrc.texas.gov catalog only; no auto-download"],
        ],
        [38, 28, 22, 52],
    )
    pdf.body(
        "Bonus: Census CBP (County Business Patterns) also works with CENSUS_API_KEY. "
        "Legacy FBI SAPI (api.usa.gov/crime/fbi/sapi) returns 404 - use CDE summarized endpoints instead. "
        "HPMS geospatial dataset 4dez-3n4e on BTS is non-tabular; use HPMS County Summary 8j5p-a5aj instead."
    )

    pdf.sub_title("Sample live values (DFW pilot counties)")
    pdf.mono_block(
        "county     | population | mean_aadt | zillow_zhvi | fhfa_hpi | blm_leases | road_miles\n"
        "Dallas     | 2,621,179  | 50,050    | $312,652    | 986      | 97         | 6,248\n"
        "Tarrant    | 2,167,390  | 40,490    | $325,761    | 882      | 321        | 6,414\n"
        "Collin     | 1,163,337  | 32,962    | $488,699    | 852      | 142        | 3,599\n"
        "Denton     |   979,561  | 32,839    | $444,147    | 825      | 325        | 3,411\n"
        "Rockwall   |   123,617  | 24,644    | $417,027    | 573      | 20         | 532"
    )
    pdf.body(
        "Outputs: data/raw/*.csv (per source), data/processed/county_features.csv (stitched), "
        "exports/county_dashboard.csv (Power BI), data/location_intelligence.db (SQLite). "
        "Run: python scripts/probe_sources.py (connectivity) or python -m src.run_pipeline (full pull)."
    )

    pdf.table(
        ["Category", "API?", "Cost", "Best granularity", "Pilot result"],
        [
            ["Census population", "Yes (1 key)", "Free", "Block group / tract", "WORKING"],
            ["Traffic", "Partial (no key)", "Free", "Road segment / county", "WORKING"],
            ["Crime", "Yes (data.gov)", "Free", "State rates (agency TBD)", "WORKING*"],
            ["Housing prices", "Partial (no key)", "Free", "County / tract", "WORKING"],
            ["Mineral rights", "Limited (no key)", "Free", "Lease bbox / bulk", "PARTIAL"],
        ],
        [34, 22, 16, 38, 30],
    )
    pdf.body("*Crime: live state-level rates via FBI CDE; county-level requires agency crosswalk (not yet built).")

    # 1. CENSUS
    pdf.add_page()
    pdf.section_title("1. Census Data - Populations")
    pdf.sub_title("Primary public sources")
    pdf.table(
        ["Source", "Access", "API", "Cost", "Granularity"],
        [
            ["ACS 5-Year", "api.census.gov", "Yes", "Free", "Nation -> block group"],
            ["ACS 1-Year", "api.census.gov", "Yes", "Free", "65k+ pop areas"],
            ["Decennial Census", "api.census.gov", "Yes", "Free", "Block"],
            ["Population Estimates (PEP)", "api.census.gov/pep/charv", "Yes", "Free", "County"],
            ["CBP (business)", "api.census.gov", "Yes", "Free", "County, ZIP"],
        ],
        [34, 34, 16, 16, 40],
    )
    pdf.body(
        "API key required (free): https://api.census.gov/data/key_signup.html. Activation email link may be "
        "required; keys can take hours to become active. Rate limits apply (~500 queries/day without key historically; "
        "higher with registered key)."
    )
    pdf.sub_title("Recommended variables for site selection")
    pdf.body(
        "Population (B01001_001E), median household income (B19013_001E), households (B11001_001E), "
        "median home value (B25077_001E), commute time (B08303), age distribution, education, renter/owner mix."
    )
    pdf.sub_title("Sample API response (ACS 5-Year, Dallas County, TX)")
    pdf.mono_block(
        'GET https://api.census.gov/data/2024/acs/acs5\n'
        '  ?get=NAME,B01001_001E,B19013_001E\n'
        '  &for=county:113&in=state:48&key=YOUR_KEY\n\n'
        '[\n'
        '  ["NAME","B01001_001E","B19013_001E","state","county"],\n'
        '  ["Dallas County, Texas","2621179","76547","48","113"]\n'
        ']'
    )
    pdf.sub_title("Sample county-level record (DFW pilot - live pull)")
    pdf.mono_block(
        "county_fips | county_name              | population | median_income | households\n"
        "48085       | Collin County, Texas     | 1,163,337  | 121,600       | 416,646\n"
        "48113       | Dallas County, Texas     | 2,621,179  | 76,547        | 982,737\n"
        "48439       | Tarrant County, Texas    | 2,167,390  | 84,207        | 782,419"
    )
    pdf.body("Verdict: WORKING in pilot. ACS + PEP + CBP all confirmed with CENSUS_API_KEY. Dallas PEP 2023: 2,606,358.")

    # 2. TRAFFIC
    pdf.add_page()
    pdf.section_title("2. Traffic Data")
    pdf.sub_title("Primary public sources")
    pdf.table(
        ["Source", "Access", "API", "Cost", "Granularity"],
        [
            ["FHWA HPMS", "geo.dot.gov ArcGIS REST", "Yes (no key)", "Free", "Road segment"],
            ["BTS NTAD County Summary", "data.transportation.gov/8j5p-a5aj", "Yes (no key)", "Free", "County miles"],
            ["BTS NTAD geospatial", "data.transportation.gov/4dez-3n4e", "No (non-tabular)", "Free", "Road segment GIS"],
            ["TxDOT Roadway Inventory", "txdot.gov", "Bulk / reports", "Free", "County, road"],
            ["BTS TranStats", "transtats.bts.gov", "Download", "Free", "Airport-centric"],
            ["INRIX / HERE", "Commercial", "Paid API", "Paid", "Real-time segment"],
        ],
        [34, 38, 24, 16, 38],
    )
    pdf.body(
        "Pilot fix: use lowercase field county_code (not COUNTY_CODE) on geo.dot.gov Texas FeatureServer. "
        "Example: where=county_code=113 AND aadt>0 returns live segments. County aggregation no longer "
        "requires shapefile download for the pilot - REST pagination is sufficient. BTS county summary "
        "dataset 8j5p-a5aj provides systemlength by stateid + countyid (3-digit FIPS suffix)."
    )
    pdf.sub_title("Sample HPMS segment record")
    pdf.mono_block(
        "route_id     | county_code | aadt  | func_class | lanes | speed_limit\n"
        "IH0030-KG    | 48113       | 245000| 11 (Interstate) | 8  | 65\n"
        "US0075-LX    | 48085       | 42800 | 14 (Principal Arterial) | 4 | 55\n"
        "FM0543       | 48397       | 12400 | 16 (Collector) | 2 | 45"
    )
    pdf.sub_title("Sample county aggregation (live pilot pull)")
    pdf.mono_block(
        "county_fips | mean_aadt | max_aadt | p90_aadt | segment_count | ntad_system_miles\n"
        "48113       | 50,050    | 267,131  | 148,977  | 12,787        | 6,248\n"
        "48085       | 32,962    | 231,767  | 97,073   | 4,165         | 3,599\n"
        "48439       | 40,490    | 213,306  | 124,035  | 10,870        | 6,414"
    )
    pdf.body("Verdict: WORKING in pilot. FHWA ArcGIS + BTS NTAD county summary both return live county data without API keys.")

    # 3. CRIME
    pdf.add_page()
    pdf.section_title("3. Crime Data")
    pdf.sub_title("Primary public sources")
    pdf.table(
        ["Source", "Access", "API", "Cost", "Granularity"],
        [
            ["FBI Crime Data Explorer", "cde.ucr.cjis.gov", "Yes", "Free", "Agency, state, national"],
            ["FBI SAPI (legacy)", "api.usa.gov/crime/fbi/sapi", "Unstable", "Free", "Agency, state"],
            ["BJS/NIBRS", "bjs.ojp.gov", "Bulk", "Free", "Agency / incident"],
            ["State UCR portals", "Varies", "Varies", "Free", "Agency / city"],
            ["City open data", "data.gov / city portals", "Often yes", "Free", "Precinct / tract"],
        ],
        [36, 38, 20, 14, 42],
    )
    pdf.body(
        "Crime is reported by ~18,000 law enforcement agencies voluntarily. County-level statistics are not "
        "published uniformly - you must map agency ORI codes to counties and roll up, or use state/national "
        "estimates. NIBRS provides incident-level detail (location type, offense, victim demographics) but "
        "coverage is incomplete. API key: free via api.data.gov."
    )
    pdf.sub_title("Sample CDE API response (live pilot - Texas violent crime rates)")
    pdf.mono_block(
        'GET https://api.usa.gov/crime/fbi/cde/summarized/state/TX/violent-crime\n'
        '  ?api_key=DATA_GOV_KEY&from=01-2023&to=12-2023\n\n'
        '{"offenses":{"rates":{"Texas Offenses":{"01-2023":35.24,"02-2023":30.97,...}}}}'
    )
    pdf.sub_title("Sample state estimate record (applied to all pilot counties)")
    pdf.mono_block(
        "county_fips | violent_rate_per_100k | property_rate | crime_source\n"
        "48113       | 34.68                  | 189.39        | FBI CDE summarized (state monthly rates)\n"
        "48085       | 34.68                  | 189.39        | FBI CDE summarized (state monthly rates)"
    )
    pdf.body(
        "Caveat: Legacy api.usa.gov/crime/fbi/sapi returns 404 in pilot tests. "
        "CDE summarized endpoints work with DATA_GOV_API_KEY. "
        "Verdict: WORKING for state-level rates; county stitching still requires agency ORI crosswalk."
    )

    # 4. HOUSING PRICES
    pdf.add_page()
    pdf.section_title("4. Housing Prices")
    pdf.sub_title("Primary public sources")
    pdf.table(
        ["Source", "Access", "API", "Cost", "Granularity"],
        [
            ["FHFA House Price Index", "fhfa.gov/hpi/download/annual/hpi_at_county.csv", "Bulk XLSX", "Free", "County (annual)"],
            ["FRED (FHFA mirror)", "fred.stlouisfed.org", "Yes", "Free", "National, MSA, some county"],
            ["Census ACS", "api.census.gov", "Yes", "Free", "Tract+ (median value/rent)"],
            ["Zillow ZHVI", "zillow.com/research/data", "CSV download", "Free*", "ZIP, county, metro"],
            ["Redfin Data Center", "redfin.com/news/data-center", "CSV download", "Free*", "ZIP, county, metro"],
            ["CoreLogic / CoStar", "Commercial", "Paid", "Paid", "Parcel / property"],
        ],
        [36, 40, 24, 14, 36],
    )
    pdf.body(
        "*Zillow/Redfin free for research with attribution; commercial redistribution restricted. "
        "FHFA HPI is a repeat-sales index (appreciation), not a median sale price. ACS median home value "
        "is survey-based. For site selection, combining FHFA (trends) + ACS (levels) + building permits (growth) "
        "is a strong free stack."
    )
    pdf.sub_title("Sample FHFA HPI record (annual county XLSX - live pilot)")
    pdf.mono_block(
        "county_fips | county_name | fhfa_hpi_year | fhfa_hpi_index_nsa\n"
        "48113       | Dallas      | 2025          | 986.07\n"
        "48085       | Collin      | 2025          | 851.85\n"
        "48439       | Tarrant     | 2025          | 882.23"
    )
    pdf.sub_title("Sample Zillow ZHVI record (live pilot)")
    pdf.mono_block(
        "county_fips | zillow_region_name | zillow_zhvi  | zillow_zhvi_month\n"
        "48085       | Collin County      | $488,699     | 2026-05-31\n"
        "48113       | Dallas County      | $312,652     | 2026-05-31"
    )
    pdf.sub_title("Sample ACS housing record (DFW pilot)")
    pdf.mono_block(
        "county_fips | median_home_value | households | building_permits_2025\n"
        "48085       | 475,600           | 416,646    | 19,082\n"
        "48113       | 303,000           | 982,737    | 12,691"
    )
    pdf.sub_title("Sample FRED API call (building permits - growth proxy)")
    pdf.mono_block(
        'GET https://api.stlouisfed.org/fred/series/observations\n'
        '  ?series_id=BPPRIV048113&api_key=KEY&file_type=json\n\n'
        '{"date":"2025-01-01","value":"12691"}  // Dallas County permits'
    )
    pdf.body(
        "Note: FHFA monthly hpi_master.csv no longer contains county rows in 2026; use annual county XLSX instead. "
        "Verdict: WORKING in pilot. FHFA county XLSX + Zillow CSV + FRED permits + ACS values - no extra keys beyond Census/FRED."
    )

    # 5. MINERAL RIGHTS
    pdf.add_page()
    pdf.section_title("5. Mineral Rights")
    pdf.sub_title("Primary public sources")
    pdf.table(
        ["Source", "Access", "API", "Cost", "Granularity"],
        [
            ["TX Railroad Commission (RRC)", "rrc.texas.gov", "Bulk / queries*", "Free", "Well / lease / API #"],
            ["County clerk deed records", "County portals", "No unified API", "Free-fee", "Instrument / tract"],
            ["BLM MLRS (federal)", "gis.blm.gov", "ArcGIS REST", "Free", "Federal lease / section"],
            ["EIA / USGS", "eia.gov / usgs.gov", "API / bulk", "Free", "Basin / county stats"],
            ["Commercial (TexasFile, etc.)", "Private", "Paid API", "Paid", "Lease / owner / deed"],
        ],
        [38, 36, 26, 14, 36],
    )
    pdf.body(
        "*RRC explicitly prohibits automated scraping of interactive query systems. Bulk ASCII/JSON datasets "
        "are available for download (wellbore, production, permits) but mineral ownership is not a single "
        "field - it must be reconstructed from deed chains, leases, assignments, and probate records at the "
        "county level. There is no national 'mineral rights API' equivalent to Census."
    )
    pdf.sub_title("Sample RRC wellbore record (bulk download)")
    pdf.mono_block(
        "api_number  | county | lease_name      | operator         | well_type | completion_date\n"
        "42-113-12345| DALLAS | SMITH UNIT 1    | DEVON ENERGY     | OIL       | 2019-04-15\n"
        "42-085-67890| COLLIN | JOHNSON LEASE   | PIONEER NATURAL  | GAS       | 2021-08-22"
    )
    pdf.sub_title("Sample county deed / mineral instrument (courthouse record)")
    pdf.mono_block(
        "instrument_type | grantor          | grantee           | legal_description\n"
        "Mineral Deed    | Smith Family Tr. | ABC Minerals LLC  | Sec 12, Blk 33, T2S, Abstract 1234, Ector Co.\n"
        "OG Lease        | Jones Ranch      | XYZ Energy Inc.   | Sec 8, Blk 41, T1N, Abstract 567, Midland Co."
    )
    pdf.sub_title("Sample BLM federal lease count (live pilot - Dallas bbox)")
    pdf.mono_block(
        "county_fips | blm_lease_count | blm_lease_acres | query_method\n"
        "48113       | 97              | 111,829         | GEO_STATE=TX + county bbox envelope\n"
        "48439       | 321             | 152,902         | GEO_STATE=TX + county bbox envelope"
    )
    pdf.sub_title("Texas RRC pilot status")
    pdf.mono_block(
        "county_fips | rrc_source_file | rrc_well_count | note\n"
        "48113       | api113.dbf      | (empty)        | Listed on MFT; download needs browser session\n"
        "48085       | api085.dbf      | (empty)        | Catalog confirmed at mft.rrc.texas.gov public share"
    )
    pdf.body(
        "Verdict: BLM WORKING via ArcGIS spatial query (no key). RRC PARTIAL - catalog accessible, "
        "programmatic DBF download blocked by GoDrive PrimeFaces. Manual workaround: place DBF files in data/raw/rrc_cache/."
    )

    # Recommendations
    pdf.add_page()
    pdf.section_title("6. Integration Status (Post-Pilot)")
    pdf.body(
        "Implemented and working in location-intelligence pipeline:\n"
        "- Census ACS + PEP + CBP (CENSUS_API_KEY)\n"
        "- FRED building permits (FRED_API_KEY)\n"
        "- FBI CDE crime state rates (DATA_GOV_API_KEY)\n"
        "- FHFA county HPI XLSX, Zillow ZHVI CSV (no key)\n"
        "- FHWA HPMS ArcGIS AADT, BTS NTAD county miles (no key)\n"
        "- BLM MLRS lease counts by county bbox (no key)\n\n"
        "Not yet fully automated:\n"
        "- Texas RRC per-county well counts (MFT download)\n"
        "- FBI crime at county level (agency ORI crosswalk)\n"
        "- Mineral ownership from county deed chains (separate project)"
    )

    pdf.sub_title("API keys required (.env)")
    pdf.mono_block(
        "CENSUS_API_KEY   -> api.census.gov (ACS, PEP, CBP) - free signup\n"
        "FRED_API_KEY     -> fred.stlouisfed.org (building permits) - free signup\n"
        "DATA_GOV_API_KEY -> api.data.gov (FBI CDE crime) - free signup\n\n"
        "No key needed: FHFA, Zillow, FHWA HPMS, BTS NTAD, BLM MLRS, RRC catalog"
    )
    pdf.sub_title("Join keys for stitching")
    pdf.mono_block(
        "Census ACS       | GEOID (state+county+tract)| county_fips (5-digit)\n"
        "Traffic (HPMS)   | spatial intersection      | county_fips\n"
        "Crime (FBI)      | agency ORI -> county map   | state_fips\n"
        "Housing (FHFA)   | county FIPS / tract GEOID | place_name\n"
        "Mineral (RRC)    | API well number           | legal description (section/block)"
    )

    pdf.sub_title("Data gaps to flag in dashboards")
    pdf.body(
        "- Crime: not all agencies report; county rates may be missing or estimated.\n"
        "- Traffic: segment-level source data; county mean AADT is an aggregation choice.\n"
        "- Housing: ACS median value is survey-based; FHFA HPI is an index, not a dollar price.\n"
        "- Mineral rights: public data shows activity (wells, leases) more reliably than ownership."
    )

    pdf.section_title("Sources")
    pdf.set_font("Helvetica", "", 7)
    pdf.body(
        "U.S. Census Bureau - api.census.gov, acs/acs5, pep\n"
        "FHWA HPMS - fhwa.dot.gov/policyinformation/hpms\n"
        "BTS NTAD - data.transportation.gov\n"
        "FBI Crime Data Explorer - cde.ucr.cjis.gov\n"
        "FHFA HPI - fhfa.gov/data/hpi\n"
        "FRED API - fred.stlouisfed.org/docs/api/fred/\n"
        "Zillow Research - zillow.com/research/data\n"
        "Texas RRC - rrc.texas.gov/resource-center/research\n"
        "BLM MLRS - gis.blm.gov"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(OUTPUT)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build_report()
