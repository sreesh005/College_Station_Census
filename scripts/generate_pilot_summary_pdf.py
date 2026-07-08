"""Generate a short Mineral Rights Pilot Summary PDF."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Mineral_Rights_Pilot_Summary.pdf"


def _ascii(s: str) -> str:
    return (
        s.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


class SummaryPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 8, "Texas Mineral Rights - Pilot Summary", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(20, 20, 20)
        self.cell(0, 10, _ascii(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def h2(self, text: str) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(35, 35, 35)
        self.cell(0, 8, _ascii(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 4.5, _ascii(text))
        self.ln(1)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
        self.set_font("Helvetica", "B", 7.5)
        self.set_fill_color(235, 240, 248)
        for i, header in enumerate(headers):
            self.cell(widths[i], 6, _ascii(header), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 7)
        fill = False
        for row in rows:
            if self.get_y() > 265:
                self.add_page()
            x0, y0 = self.get_x(), self.get_y()
            x = x0
            line_h = 4
            wrapped = []
            for i, cell in enumerate(row):
                lines = self.multi_cell(widths[i], line_h, _ascii(cell), dry_run=True, output="LINES")
                wrapped.append(lines)
            rh = max(len(lines) for lines in wrapped) * line_h
            for i, lines in enumerate(wrapped):
                self.set_xy(x, y0)
                self.multi_cell(widths[i], line_h, _ascii("\n".join(lines)), border=1, fill=fill)
                x += widths[i]
            self.set_xy(x0, y0 + rh)
            fill = not fill
        self.ln(2)


def build() -> None:
    pdf = SummaryPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.h1("Texas Mineral Ownership Data - Pilot Summary")
    pdf.body(
        "Location Intelligence pilot | July 2026\n"
        "Question: Can Texas mineral ownership data be harvested from county records at small scale, "
        "and what limits apply at scale?"
    )

    pdf.h2("Executive Answer")
    pdf.body(
        "Yes - small-scale county index harvest is confirmed. Mineral ownership lives in county clerk "
        "Official Public Records (deeds, reservations, O&G leases, assignments), not in RRC well data. "
        "There is no statewide API; 254 counties use different vendors. Scale is an engineering + money "
        "problem, not an impossible wall - except for pre-digitization records that exist only in books "
        "or microfilm."
    )

    pdf.h2("Harvest Proof (Demonstrated)")
    proof_rows = [
        ["Courthouse index (GovOS)", "150 rows", "Reeves + Midland via browser search"],
        ["Mineral-related subset", "16 rows", "MINERAL DEED, CONVEYANCE, O&G LEASE, etc."],
        ["Example record", "2019017441", "NEECE JOHN R -> BRIGHAM MINERALS LLC | MINERAL DEED | 10/22/2019"],
        ["RRC wells (not ownership)", "100+ rows", "Midland api165.dbf + 200 GIS wells"],
    ]
    pdf.table(["Source", "Result", "Notes"], proof_rows, [42, 28, 110])
    pdf.body(
        "Plain HTTP scraping of GovOS portals returns no index rows. Browser automation works. "
        "Output: data/samples/courthouse_mineral_index_harvest.csv\n"
        "Re-run: python scripts/harvest_courthouse_demo.py"
    )

    pdf.h2("Where Mineral Ownership Actually Lives")
    pdf.body(
        "- County Clerk OPR: mineral deeds, reservations, O&G leases, royalty deeds, probates\n"
        "- NOT RRC: wells, permits, production (regulatory activity only)\n"
        "- NOT BLM MLRS: federal lease counts (spatial), not private title\n"
        "- Vendors aggregate counties: CourthouseDirect, TexasFile, Enverus"
    )

    pdf.add_page()
    pdf.h2("Limits Matrix")
    limit_rows = [
        ["Technical", "JS portals, no shared API, bot throttling", "Soft", "Browser automation or bulk FTP"],
        ["Pay", "Index often free; images ~$1/page; bulk FTP fees", "Real cost", "Reeves $50/wk; Harris Data Sales"],
        ["Legal", "Facts are public record; vendor ToS may restrict bots", "Soft", "PIA request or clerk permission"],
        ["Hard gap", "Pre-digitization books/microfilm only", "Hard", "In-person imaging or paid vendor"],
    ]
    pdf.table(["Type", "Detail", "Severity", "Workaround"], limit_rows, [24, 72, 22, 62])

    pdf.h2("County Fragmentation")
    pdf.body(
        "Each county is its own integration. Examples from pilot:\n"
        "- GovOS/Neumo: Reeves, Midland, Tarrant, Collin, Denton (publicsearch.us)\n"
        "- Tyler: Rockwall (tylerhost.net)\n"
        "- Custom: Harris (cclerk.hctx.net)\n"
        "No Texas mineral rights API exists."
    )

    pdf.h2("Key Clerk Contacts (Bulk / Data Sales)")
    contact_rows = [
        ["Reeves", "countyclerk@reevescounty.org", "432-287-0222", "FTP $50/wk or $200/mo"],
        ["Harris", "datasales@cco.hctx.net", "713-274-6390", "Pipe index + TIFF; monthly FTP"],
        ["Fort Bend", "cclerkrecords@fortbendcountytx.gov", "281-341-8685", "FTP $10-20/mo + $50 setup"],
        ["Tarrant", "wm-countyclerk@tarrantcountytx.gov", "817-884-1069", "Pay online, call to finish"],
        ["Midland", "ccland@co.midland.tx.us", "432-688-4401", "Ask for bulk/PIA terms"],
        ["Dallas", "recording@dallascounty.org", "214-653-7099", "Large batches; PIA via CC-Inquiry@"],
    ]
    pdf.table(["County", "Email", "Phone", "Bulk notes"], contact_rows, [22, 58, 28, 72])

    pdf.h2("What to Ask Clerks")
    pdf.body(
        "1. Machine-readable OPR index export (CSV/pipe-delimited)? Fields included?\n"
        "2. Filter by doc type (mineral deed, O&G lease, assignment, royalty)?\n"
        "3. Bulk images (TIFF/PDF) available separately or bundled?\n"
        "4. FTP/SFTP subscription? Setup fee, update frequency, incremental vs full?\n"
        "5. Electronic coverage date range? Any index-only or missing-image periods?\n"
        "6. Fee schedule and turnaround? Sample file or data dictionary available?"
    )

    pdf.h2("Recommended Next Steps")
    pdf.body(
        "1. Purchase Reeves weekly FTP ($50) as cheapest bulk proof from source\n"
        "2. Email Harris Data Sales and Midland ccland for bulk index quotes\n"
        "3. Pilot 3-5 counties via browser harvest OR bulk purchase (not both everywhere)\n"
        "4. Join RRC well data to courthouse leases by legal description (expect fuzzy matches)\n"
        "5. For statewide scale: evaluate CourthouseDirect or TexasFile vs build county-by-county"
    )

    pdf.h2("Related Project Files")
    pdf.body(
        "reports/Courthouse_Contact_Outreach.md - full contact guide\n"
        "reports/Mineral_Rights_Harvest_and_Limits_Report.pdf - detailed limits catalog\n"
        "reports/Texas_Mineral_Rights_Data_Strategy.pdf - three-tier build/buy plan\n"
        "data/samples/courthouse_mineral_index_harvest.csv - live harvest sample\n"
        "data/samples/courthouse_contacts.csv - contact spreadsheet"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
