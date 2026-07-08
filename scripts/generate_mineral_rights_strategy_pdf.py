"""Generate Texas Mineral Rights Data Strategy PDF (three-tier plan)."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Texas_Mineral_Rights_Data_Strategy.pdf"


class StrategyPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            8,
            "Texas Mineral Rights - Three-Tier Data Strategy",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
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
    pdf = StrategyPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Texas Mineral Rights Data Strategy", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Three-Tier Plan: Free RRC, County Scraping, Commercial Licensing", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.body(
        "Prepared for: Location Intelligence project (statewide Texas focus)\n"
        "Date: July 6, 2026\n"
        "Scope: How to obtain wells, leases, operators, and courthouse mineral ownership data"
    )

    pdf.section_title("Executive Summary")
    pdf.body(
        "Your three-tier model is correct. Texas has no statewide courthouse API for mineral ownership. "
        "The practical path is: (1) pull free RRC bulk data immediately for wells/leases/operators; "
        "(2) build county-specific scrapers for deed and grantor-grantee indexes in a handful of "
        "well-digitized counties; (3) parallel-track commercial licensing conversations to avoid "
        "years of scraper maintenance. Important nuance: RRC data shows regulatory activity, not "
        "mineral title. Courthouse deeds show ownership transfers. Neither alone equals full chain of title."
    )

    pdf.table(
        ["Tier", "Effort", "Cost", "What you get", "Ownership?"],
        [
            ["1 - Free RRC", "Low", "Free", "Wells, APIs, leases, operators, permits", "No - activity only"],
            ["2 - Scraping", "High", "Free (+ dev time)", "Deed index, grantor/grantee, doc metadata", "Partial - index, not parsed title"],
            ["3 - Buy", "Low ops", "Paid", "Statewide indexes, images, title tools", "Yes - with commercial tools"],
        ],
        [22, 22, 22, 62, 42],
    )

    # TIER 1
    pdf.add_page()
    pdf.section_title("Tier 1 - Free: Texas Railroad Commission (RRC)")
    pdf.body(
        "Build immediately. No contracts. RRC is the state oil and gas regulator. Bulk ASCII, DBF, "
        "and shapefile datasets update on published schedules (daily to weekly depending on product)."
    )

    pdf.sub_title("How to attain RRC data")
    pdf.body(
        "1. Start at the RRC Data Sets page (master index of all bulk downloads).\n"
        "2. Follow the MFT (GoDrive) HTTPS link for each dataset - no login required for free sets.\n"
        "3. Download to data/raw/rrc_cache/ and parse with Python (dbfread for DBF, pandas for ASCII).\n"
        "4. Join to counties using API number (first digits encode county) or spatial join on well shapefiles."
    )

    pdf.mono_block(
        "Master index:\n"
        "  https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/\n\n"
        "Statewide API Data (per-county DBF, twice weekly):\n"
        "  https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674\n"
        "  Files: api113.dbf (Dallas), api439.dbf (Tarrant), etc.\n\n"
        "Other high-value free sets on same page:\n"
        "  - Full Wellbore (ASCII, weekly)\n"
        "  - Drilling Permit Master (ASCII, monthly)\n"
        "  - Well Layers by County (shapefile, twice weekly)\n"
        "  - Oil and Gas Field Rules (ASCII, monthly)\n"
        "  - Completion Information (ASCII, nightly)"
    )

    pdf.sub_title("Priority RRC datasets for location intelligence")
    pdf.table(
        ["Dataset", "Update", "Key fields", "Use case"],
        [
            ["Statewide API Data", "2x/week", "API #, lease, survey, plug date", "Well count by county"],
            ["Full Wellbore", "Weekly", "API, depth, status, county", "Active vs plugged inventory"],
            ["Drilling Permits", "Monthly", "Permit #, API, lat/lon, field", " New activity / growth"],
            ["Well Layers shapefile", "2x/week", "Geometry, API, lease name", "Map wells to parcels"],
            ["Production Data Query", "Monthly", "Lease, operator, volumes", "Producing vs non-producing"],
        ],
        [38, 22, 52, 48],
    )

    pdf.sub_title("RRC download caveat (known issue)")
    pdf.body(
        "The MFT GoDrive portal uses PrimeFaces web forms. Programmatic single-file download may require "
        "a browser session or manual download. Workarounds: (a) manual download of target county DBF files; "
        "(b) use Full Wellbore statewide ASCII instead of per-county DBF; (c) use Well Layers shapefile zip "
        "and filter by county FIPS in geopandas."
    )

    pdf.sub_title("Sample pipeline command (after fetch_rrc.py is extended)")
    pdf.mono_block(
        "python -m src.fetch_rrc_wells          # per-county API DBF\n"
        "python -m src.fetch_rrc_wellbore       # statewide ASCII (recommended)\n"
        "python -m src.fetch_rrc_permits        # drilling permits with lat/lon"
    )

    # TIER 2
    pdf.add_page()
    pdf.section_title("Tier 2 - Scraping: Target County Clerk Portals")
    pdf.body(
        "Pick 3-5 counties with the deepest digitization and highest mineral activity. Records are public "
        "under Texas Public Information Act, but each county uses different software. Expect per-county "
        "scraper maintenance, login requirements, rate limits, and terms-of-use review before automating."
    )

    pdf.sub_title("Recommended pilot counties")
    pdf.table(
        ["County", "Portal", "Vendor", "Online depth", "Mineral relevance"],
        [
            ["Harris", "cclerk.hctx.net/WebSearch", "Custom (Harris)", "Images from 1960", "Urban + legacy O&G"],
            ["Midland", "midland.tx.publicsearch.us", "GovOS/Kofile", "Full land records", "Permian core"],
            ["Tarrant", "tarrant.tx.publicsearch.us", "GovOS/Kofile", "Real property + OCR", "DFW + Barnett"],
            ["Ector (add)", "ectorcountytx-web.tylerhost.net", "Tyler EagleWeb", "Odessa / Permian", "High well density"],
            ["Reeves (add)", "reeves.tx.publicsearch.us", "GovOS/Kofile", "All land online + FTP bulk", "Delaware Basin"],
        ],
        [22, 52, 28, 32, 36],
    )

    pdf.sub_title("What to scrape (index metadata - not full OCR initially)")
    pdf.mono_block(
        "Per recorded instrument:\n"
        "  - county_fips, instrument_number, recorded_date\n"
        "  - grantor, grantee, document_type\n"
        "  - book/volume/page (if available)\n"
        "  - legal_description (freeform text)\n"
        "  - image_url or doc_id (for later OCR pass)\n\n"
        "Filter document types for mineral work:\n"
        "  mineral deed, royalty deed, O&G lease, assignment,\n"
        "  ratification, release, pooling, probate, affidavit of heirship"
    )

    pdf.sub_title("How to attain courthouse index data (per county)")
    pdf.body(
        "Harris County:\n"
        "  1. Register free account at cclerk.hctx.net/Applications/WebSearch\n"
        "  2. Search Real Property by grantor/grantee or legal description\n"
        "  3. Index search is free; images $0.10/page for non-watermarked copies\n"
        "  4. Scraper target: authenticated session + RP search form POST\n\n"
        "Midland / Tarrant (GovOS PublicSearch):\n"
        "  1. Open county portal (no account usually required for index)\n"
        "  2. Use Quick Search or Advanced Search (grantor, grantee, doc type, date range)\n"
        "  3. Scraper target: search API calls behind publicsearch.us UI (JSON responses)\n"
        "  4. Enable 'Search Index & Full Text (OCR)' for keyword hits on 'minerals'\n\n"
        "Reeves County (bulk alternative):\n"
        "  1. Same publicsearch.us portal for index\n"
        "  2. Clerk also sells FTP image bundles: $50/week or $200/month\n"
        "  3. Contact: Reeves County Clerk, Pecos TX - see reevescounty.org/departments/county-clerk"
    )

    pdf.sub_title("Scraper build checklist")
    pdf.body(
        "- Map one county end-to-end before generalizing (Midland is a good first target).\n"
        "- Store raw JSON/HTML in data/raw/courthouse/{county_fips}/ with scrape timestamp.\n"
        "- Normalize to a single schema: courthouse_records.csv.\n"
        "- Respect robots.txt and rate limits (1-2 req/sec); run overnight batch jobs.\n"
        "- Budget 2-4 hours/month per county for portal upgrades and CAPTCHA changes.\n"
        "- Legal: public records are accessible, but automated bulk scraping may violate portal ToS - "
        "get a one-page opinion from counsel if scaling beyond research volumes."
    )

    # TIER 3
    pdf.add_page()
    pdf.section_title("Tier 3 - Buy vs Build: Commercial Licensing")
    pdf.body(
        "If budget allows, one email to each vendor can clarify enterprise, nonprofit, or research pricing. "
        "Commercial access often costs less than 6-12 months of scraper engineering and maintenance for "
        "statewide coverage."
    )

    pdf.sub_title("Vendor comparison")
    pdf.table(
        ["Vendor", "Coverage", "Contact", "Typical model", "Best for"],
        [
            ["CourthouseDirect", "254 TX counties", "information@courthousedirect.com", "Geo-Index $300/county/mo", "Grantor-grantee + O&G lease check"],
            ["CourthouseDirect", "(800) 925-4225", "API Integration page", "TVP plans, $1.50/doc", "Title shops, land departments"],
            ["Enverus Courthouse", "~150 TX counties", "enverus.com/products/courthouse", "Enterprise quote", "Mineral title back to sovereignty"],
            ["TexasFile", "254 clerk + 200+ mineral", "support@texasfile.com", "Bulk rolls $500/county", "Producing mineral tax rolls"],
            ["TexasFile", "(214) 705-6400", "minerals@texasfile.com", "Regional $2.5k-$20k/yr", "Excel ownership rolls (CAD-sourced)"],
        ],
        [32, 38, 42, 38, 40],
    )

    pdf.sub_title("CourthouseDirect - how to attain access")
    pdf.body(
        "1. Review Texas Volume Pricing: courthousedirect.com/TexasVolumePricing.aspx\n"
        "2. Review API Integration page: courthousedirect.com/ProductInfo/APIIntegrationInfo.aspx\n"
        "3. Email information@courthousedirect.com with:\n"
        "   - Use case: mineral ownership tracking / location intelligence\n"
        "   - Counties of interest: statewide or Permian + Harris + Tarrant\n"
        "   - Ask: API access, bulk index licensing, nonprofit/research pricing\n"
        "4. Published Geo-Index sample pricing (negotiable): $1,200/mo all counties (index only), "
        "or $300/county/month; $50/seat; $1.50/document image."
    )

    pdf.sub_title("Enverus Courthouse - how to attain access")
    pdf.body(
        "1. Visit enverus.com/products/courthouse/\n"
        "2. Request demo / pricing for Texas mineral title research\n"
        "3. Ask specifically about: programmatic export, county coverage list, sovereignty-depth "
        "counties, and API vs batch file delivery\n"
        "4. Enverus claims 150 TX counties for document search and 29+ counties indexed back to sovereignty."
    )

    pdf.sub_title("TexasFile (alternative) - mineral rolls not deed chains")
    pdf.body(
        "TexasFile is worth a parallel quote if producing-interest ownership (tax roll) is sufficient:\n"
        "- Per search: $0.25 at texasfile.com/minerals/\n"
        "- Bulk county roll: ~$500 (Excel with owner, interest %, operator, lease, legal desc)\n"
        "- Multi-county packages: $2,500-$20,000/year - email minerals@texasfile.com for sample roll\n"
        "This is faster than deed scraping but does not replace chain-of-title from courthouse instruments."
    )

    pdf.sub_title("Sample outreach email (copy/paste)")
    pdf.mono_block(
        "Subject: API / bulk licensing inquiry - Texas mineral & courthouse records\n\n"
        "We are building a location intelligence platform that tracks oil & gas activity\n"
        "and mineral interest ownership across Texas. We are evaluating commercial data\n"
        "licensing vs building county scrapers.\n\n"
        "Please share:\n"
        "  1) API or bulk file options for grantor-grantee indexes and O&G instruments\n"
        "  2) County coverage list and update frequency\n"
        "  3) Pricing for research / nonprofit / startup use (10 users, statewide)\n"
        "  4) Sample data dictionary or trial access\n\n"
        "Target counties: Harris, Midland, Tarrant, Ector, Reeves (+ statewide if available)"
    )

    # Decision + sequence
    pdf.add_page()
    pdf.section_title("Recommended Sequence")
    pdf.body(
        "Week 1-2 (Free tier - do now):\n"
        "- Download RRC Full Wellbore + Drilling Permits statewide ASCII\n"
        "- Parse API numbers to county; load into SQLite alongside existing pipeline\n"
        "- Manually download 5 pilot county api###.dbf files from MFT if automation blocked\n\n"
        "Week 3-6 (Scraping tier - prove one county):\n"
        "- Build Midland County scraper (GovOS template, cleanest URL pattern)\n"
        "- Extract grantor/grantee index for document types: mineral deed, O&G lease, assignment\n"
        "- Validate 100 known instruments against manual portal search\n\n"
        "Week 2-4 parallel (Buy tier - one email each):\n"
        "- CourthouseDirect: API / Geo-Index pricing\n"
        "- Enverus: Courthouse enterprise demo\n"
        "- TexasFile: sample mineral roll for Midland or Ward County\n\n"
        "Decision gate (Week 6):\n"
        "- If commercial index < 6 months engineering cost -> buy\n"
        "- If not -> extend scrapers to Harris (custom) and Tarrant (GovOS), accept maintenance"
    )

    pdf.sub_title("What each tier does NOT give you")
    pdf.table(
        ["Gap", "Why it matters", "Mitigation"],
        [
            ["RRC != ownership", "Shows wells/operators, not who owns minerals", "Add courthouse deed tier"],
            ["Index != chain of title", "Grantor-grantee list is not parsed ownership %", "Build graph or buy title tool"],
            ["Scrape != 254 counties", "Each portal is different", "Commercial aggregator or phased rollout"],
            ["Tax roll != all minerals", "Non-producing severed minerals may be absent", "Deed research for dormant rights"],
        ],
        [38, 62, 60],
    )

    pdf.section_title("Key URLs (quick reference)")
    pdf.set_font("Helvetica", "", 7)
    pdf.body(
        "RRC data sets: https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/\n"
        "RRC MFT API DBF: https://mft.rrc.texas.gov/link/1eb94d66-461d-4114-93f7-b4bc04a70674\n"
        "Harris clerk: https://cclerk.hctx.net/Applications/WebSearch/Home.aspx\n"
        "Midland clerk: https://midland.tx.publicsearch.us/\n"
        "Tarrant clerk: https://tarrant.tx.publicsearch.us/\n"
        "Ector clerk: https://ectorcountytx-web.tylerhost.net/web/user/disclaimer\n"
        "Reeves clerk: https://reeves.tx.publicsearch.us/\n"
        "CourthouseDirect: https://www.courthousedirect.com/TexasVolumePricing.aspx\n"
        "Enverus Courthouse: https://www.enverus.com/products/courthouse/\n"
        "TexasFile minerals: https://www.texasfile.com/minerals/"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(OUTPUT)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build_report()
