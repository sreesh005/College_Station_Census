"""Generate Mineral Rights Harvest & Limits Report PDF."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Mineral_Rights_Harvest_and_Limits_Report.pdf"
SAMPLES = ROOT / "data" / "samples"


def _ascii(s: str) -> str:
    return (
        s.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


class ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Mineral Rights Harvest & Limits Report", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def h1(self, t: str) -> None:
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(20, 20, 20)
        self.cell(0, 10, t, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def h2(self, t: str) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, t, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, t: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 4.5, _ascii(t))
        self.ln(1)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
        self.set_font("Helvetica", "B", 7.5)
        self.set_fill_color(230, 236, 245)
        for i, h in enumerate(headers):
            self.cell(widths[i], 6, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 7)
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
            x0, y0 = self.get_x(), self.get_y()
            x = x0
            line_h = 4
            wrapped = []
            for i, cell in enumerate(row):
                lines = self.multi_cell(widths[i], line_h, _ascii(cell), dry_run=True, output="LINES")
                wrapped.append(lines)
            max_lines = max(len(x) for x in wrapped)
            rh = max_lines * line_h
            for i, lines in enumerate(wrapped):
                self.set_xy(x, y0)
                self.multi_cell(widths[i], line_h, _ascii("\n".join(lines)), border=1, fill=fill)
                x += widths[i]
            self.set_xy(x0, y0 + rh)
            fill = not fill
        self.ln(2)



def build() -> None:
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.h1("Texas Mineral Rights: Harvest Proof & Data Limits")
    pdf.body(
        "Pilot research for location-intelligence (July 2026). Goal: confirm whether mineral "
        "ownership and related O&G records can be harvested from primary sources, document limits "
        "(rate, legal, pay, hard), and collect working samples where feasible without large-scale scraping."
    )

    pdf.h2("Executive Summary")
    pdf.body(
        "1. RRC (Railroad Commission) data is broadly obtainable for free via bulk MFT downloads and "
        "ArcGIS REST - wells, permits, production, pipelines, UIC, etc. It does NOT include private "
        "mineral ownership or courthouse title chains.\n"
        "2. Courthouse mineral ownership lives in county clerk real-property indexes (deeds, reservations, "
        "O&G leases, probates). Index search is public; bulk index+images are sold county-by-county.\n"
        "3. GovOS/Kofile portals (publicsearch.us) require client-side JavaScript - no public REST API. "
        "DEMONSTRATED: Playwright browser harvest pulled 150 index rows from Reeves + Midland (16 mineral-related).\n"
        "4. No fundamental hard limit prevents obtaining Texas public records, but 254 counties x "
        "disparate vendors means statewide ownership is an aggregation problem, not a single-API problem."
    )

    pdf.h2("Samples Collected (This Pilot)")
    sample_rows = [
        ["courthouse_mineral_index_harvest.csv", "150 rows", "Reeves + Midland GovOS index via Playwright", "OK"],
        ["courthouse_mineral_only_sample.csv", "16 rows", "Mineral deed/lease/conveyance subset", "OK"],
        ["rrc_midland_wells_sample.csv", "100 rows", "RRC MFT api165.dbf (Midland wells)", "OK"],
        ["rrc_gis_midland_wells_sample.csv", "200 rows", "RRC ArcGIS Well Locations - Midland bbox", "OK"],
        ["courthouse_reeves_mineral_doctypes.csv", "644 types", "Mineral/O&G doc-type codes from Reeves portal", "OK"],
    ]
    pdf.table(["File", "Size", "Description", "Status"], sample_rows, [42, 18, 88, 22])

    pdf.body(
        "Re-run courthouse harvest: python scripts/harvest_courthouse_demo.py (requires playwright install chromium).\n"
        "Example row: NEECE JOHN R -> BRIGHAM MINERALS LLC, MINERAL DEED, doc# 2019017441, Reeves County.\n"
        "RRC MFT: use PrimeFaces ajax POST (scripts/mft_ajax_download.py). Contact: digital@rrc.texas.gov."
    )

    pdf.h2("What the RRC Provides (Full Catalog)")
    pdf.body("Free bulk datasets at rrc.texas.gov/resource-center/research/data-sets-available-for-download/")
    rrc_rows = [
        ["Digital Map Data", "Well/Survey/Pipeline/Base shapefiles by county; Statewide API ASCII/DBF", "2x/week"],
        ["Drilling Permits", "Master, trailer, daily/monthly pending; W1 images; horizontal permits", "Daily-Monthly"],
        ["Oil & Gas Field Data", "Field names, rules, annual reports, statewide field EBCDIC", "Monthly"],
        ["Production Data", "Oil/gas ledgers by district; historical ledgers; CSV query dumps", "Monthly"],
        ["Regulatory", "P-4 certs, dockets, P5 operators, R3 gas plants (JSON), Oil/ICE weekly", "Weekly-Monthly"],
        ["Well Data", "Full Wellbore (ASCII/EBCDIC ~366MB gz); wellbore query; 26-mo status; completions", "Weekly-Monthly"],
        ["Tax Incentive", "High-cost gas, NGPA, ST-1 CSV", "Monthly"],
        ["UIC", "Injection well inventory ASCII/EBCDIC", "Monthly"],
        ["GIS REST", "gis.rrc.texas.gov - wells, pipelines, surveys, districts (max 1000/query)", "Live"],
    ]
    pdf.table(["Category", "Contents", "Update"], rrc_rows, [38, 112, 30])

    pdf.h2("What RRC Does NOT Provide")
    pdf.body(
        "- Private mineral ownership, royalty fractions, or deed chains\n"
        "- Surface/mineral severance from county records\n"
        "- Coal (Texas RRC is oil/gas focused; coal is rare in TX; check GLO/federal for lignite)\n"
        "- Legal title opinions - RRC disclaimers state datasets are informational, not authoritative records"
    )

    pdf.add_page()
    pdf.h2("RRC Limits Matrix")
    rrc_limits = [
        ["Bulk MFT downloads", "None published", "Free", "Public records - intended path for volume", "No"],
        ["Online query system (webapps)", "Sessions terminated if automated", "Free", "Site policy bans robots causing degradation", "Soft - use bulk instead"],
        ["ArcGIS REST", "maxRecordCount 1000/query", "Free", "Fair use; throttle politely", "No"],
        ["EBCDIC/mainframe files", "Format conversion burden", "Free", "User must convert", "No"],
        ["Coal/mineral title", "Not in RRC scope", "n/a", "Wrong agency for ownership", "Hard for ownership"],
    ]
    pdf.table(["Channel", "Rate/Technical", "Cost", "Legal/Policy", "Hard limit?"], rrc_limits, [38, 38, 18, 58, 18])

    pdf.h2("Courthouse Mineral Ownership - Where It Lives")
    pdf.body(
        "Recorded in County Clerk Official Public Records: mineral deeds, reservations, O&G leases, "
        "assignments, royalty deeds, probates, affidavits of heirship, plats. Each of 254 counties "
        "maintains its own index; vendors include GovOS (publicsearch.us), Tyler EagleWeb, Avenu "
        "(TexasLandRecords), Harris custom portal, Kofile legacy systems."
    )

    pdf.h2("Courthouse Harvest Proof (Demonstrated)")
    pdf.body(
        "CONFIRMED via Playwright browser automation on GovOS portals (July 2026):\n"
        "- 150 index rows harvested from Reeves + Midland (50 per search x 3 searches)\n"
        "- 16 mineral-related instruments (MINERAL DEED, MINERAL CONVEYANCE, O&G LEASE, etc.)\n"
        "- Fields: grantor, grantee, doc_type, recorded_date, doc_number, legal_description\n"
        "- Method: navigate to /results?searchQuery=..., wait for JS render, parse results table\n"
        "- Plain HTTP requests alone fail; browser automation works for small-scale pilot harvest\n"
        "Reeves also preloads docTypeMappings (644 mineral/O&G codes). Clerk: 432-287-0222."
    )

    pdf.h2("Courthouse Limits Matrix")
    court_limits = [
        ["GovOS index search (manual)", "Unpublished; no API key", "Free index", "Public records; vendor ToS on images", "No for index"],
        ["Browser automation (Playwright)", "Demo: 150 rows/county search", "Free index", "Pilot proven on GovOS; scale per-county", "Soft"],
        ["Document images", "Per-page fees", "$1/pg typical", "GovOS: copies priced; Harris watermarked free online", "No"],
        ["Bulk index (pipe-delimited)", "County policy", "Varies - see below", "PIA (Gov Code 552) + Local Gov 195.007", "No"],
        ["Bulk images / FTP", "County policy", "Reeves $50/wk, $200/mo FTP", "Direct from clerk - preferred source", "No"],
        ["Statewide ownership API", "Does not exist", "Vendor subscriptions", "CourthouseDirect, Enverus, TexasFile", "Hard - no single government API"],
        ["Pre-1980s unindexed records", "In-office/microfilm", "Staff search fees", "Not all backfiles digitized", "Partial hard gap"],
    ]
    pdf.table(["Channel", "Rate/Technical", "Cost", "Legal/Policy", "Hard limit?"], court_limits, [38, 38, 28, 58, 18])

    pdf.h2("Bulk / Offline County Data (Published - Not Yet Contacted)")
    bulk_rows = [
        ["Reeves", "432-287-0222", "FTP weekly $50 / monthly $200", "reeves.tx.publicsearch.us", "Fee schedule on county site"],
        ["Harris", "713-274-6390", "Custom date-range index (pipe txt) + TIFF; monthly FTP", "cclerk.hctx.net/PublicRecords.aspx", "Data Sales desk"],
        ["Fort Bend", "County Clerk", "FTP daily $10/GB + $50 setup", "fortbendcountytx.gov", "Computer Information Fee Schedule"],
        ["Midland", "432-688-4401", "GovOS portal; bulk terms not published online", "midland.tx.publicsearch.us", "Call clerk for PIA/bulk"],
    ]
    pdf.table(["County", "Phone", "Bulk Option", "Portal", "Notes"], bulk_rows, [22, 28, 58, 52, 30])

    pdf.add_page()
    pdf.h2("Draft Clerk Outreach (Ready to Send)")
    pdf.body(
        "Subject: Public Information Act / Bulk OPR Index Request - Mineral & O&G Instruments\n\n"
        "Dear County Clerk Records Division,\n\n"
        "We are researching official public records for mineral and oil & gas title work statewide. "
        "Could you advise:\n"
        "1. Do you offer bulk export of the Official Public Records index (grantor, grantee, doc type, "
        "recorded date, instrument number, legal description) in CSV or pipe-delimited text?\n"
        "2. Is FTP or SFTP available for recurring index and/or TIFF/PDF images? Fee schedule?\n"
        "3. What date range is fully indexed online vs. in-office only?\n"
        "4. For PIA requests, what is your per-page/per-file cost cap and typical turnaround?\n\n"
        "We prefer going directly to the county rather than third-party aggregators.\n\n"
        "Thank you,\n[Your name / organization]"
    )

    pdf.h2("Hard vs Soft Limits - Can a Million Computers Get It All?")
    pdf.body(
        "Soft limits (scale with money, time, or polite engineering):\n"
        "- RRC online query throttling - bypass via free bulk MFT\n"
        "- GovOS bot detection - bypass via bulk FTP purchase or PIA\n"
        "- 254 county schemas - bypass via vendor aggregation ($$) or phased county rollout\n"
        "- Image costs at $1/page - bypass via bulk image subscriptions\n\n"
        "Hard / structural limits:\n"
        "- No statewide mineral ownership register exists in Texas law\n"
        "- Ownership must be reconstructed from chains of title, not queried like well API numbers\n"
        "- Unrecorded leases/title gaps are inherently invisible in any public index\n"
        "- Federal minerals (BLM) and state minerals (GLO) are separate from county OPR\n"
        "- Pre-digitization records may exist only in books/microfilm with manual lookup\n\n"
        "Conclusion: Volume is solvable; complete automated ownership for all tracts is not - title "
        "research remains interpretive even with full index access."
    )

    pdf.h2("Recommended Next Steps")
    pdf.body(
        "1. Wire harvest_courthouse_demo.py into pipeline for pilot counties (Reeves, Midland, Tarrant)\n"
        "2. Purchase Reeves weekly FTP ($50) for bulk index without per-search browser overhead\n"
        "3. Send PIA/bulk inquiry to Midland + Harris Data Sales (713-274-6390)\n"
        "4. Integrate RRC well data with courthouse leases by legal description (expect fuzzy joins)\n"
        "5. Scale to additional GovOS counties using same Playwright pattern"
    )

    pdf.h2("Sample File Locations")
    pdf.body(
        f"Project: {ROOT}\n"
        f"  data/samples/courthouse_mineral_index_harvest.csv - 150 courthouse index rows\n"
        f"  data/samples/courthouse_mineral_only_sample.csv - 16 mineral-related rows\n"
        f"  data/samples/rrc_midland_wells_sample.csv - 100 RRC wells from MFT DBF\n"
        f"  scripts/harvest_courthouse_demo.py - re-run courthouse harvest demo\n"
        f"  reports/Texas_Mineral_Rights_Data_Strategy.pdf - three-tier build/buy plan"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
