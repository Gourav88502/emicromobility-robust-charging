"""
build_executive_summary.py
===========================
Generates the 2-page ANONYMISED Executive Summary for the Level-1 blind review,
laid out EXACTLY against the competition's official template:

    Team Name  ->  Title  ->  Approach (<=300 words)  ->  Outcomes (<=500 words)
    ->  Links to GitHub files  ->  References (not counted in the word limit)

Formatting per the template: A4, 25.4 mm margins, font Aptos 11 pt. Schematic
diagrams and data visualisations do not count towards the 2 pages / word limit.

Two renderers from ONE content source, so they never drift:
  * Executive_Summary.docx  — authoritative, in Aptos (open in Word -> Save as PDF
    to guarantee the Aptos font for the final submission).
  * Executive_Summary.pdf   — ready-to-send backup rendered with reportlab.

All numbers are read live from outputs/results.json.

    python scripts/build_executive_summary.py
"""

from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
RESULTS = json.loads((OUT / "results.json").read_text(encoding="utf-8"))

# --------------------------------------------------------------------------- #
#  Anonymised identity  (NO personal / institution details — blind review)
# --------------------------------------------------------------------------- #
TEAM_NAME = "Team SolarCycle"        # anonymised alias for the blind Level-1 review
GITHUB_URL = "https://github.com/Gourav88502/emicromobility-robust-charging"

TITLE = ("Robust, Solar-Powered Charging Infrastructure for a Shared e-Bike "
         "Scheme under Demand Uncertainty")
SUBTITLE = ("Theme 3 (primary): solar-PV charging-station design  ·  "
            "Theme 2 (secondary): managed charge/discharge profiles   |   "
            "Example site: University of Warwick, Coventry (CV4 7AL)")


# --------------------------------------------------------------------------- #
#  Content (defined once; rendered to both .docx and .pdf)
# --------------------------------------------------------------------------- #
def _content() -> dict:
    rec = RESULTS["recommended_design"]
    nai = RESULTS["naive_design"]
    vor = RESULTS["value_of_robustness"]
    emis = RESULTS["emissions"]
    rob = RESULTS["robustness_of_robustness"]
    capex = RESULTS["recommended_capex_gbp"]
    mc = RESULTS["monte_carlo"]
    val = RESULTS["validation"]["metrics_within_published_range"]
    lp = RESULTS.get("optimal_control", {}).get("max_grid_cost_saving_pct")
    lp_txt = (f"; an optimal LP controller confirms managed charging cuts grid-energy "
              f"cost by up to {lp:.0f}% versus unmanaged charging" if lp else "")
    perf = RESULTS["recommended_performance_high_scenario"]
    sb = rob.get("storage_boundary_grid_kW")
    sb_txt = (f"about {sb:g} kW or weaker" if sb else "near off-grid")
    t2 = RESULTS.get("theme2_route", {})
    pr = t2.get("profiles", {})
    p_efc = pr.get("personal_efc_per_yr", 0); s_efc = pr.get("shared_efc_per_yr", 0)
    ratio = (s_efc / p_efc) if p_efc else 1.3

    approach = [
        [("Aim. ", True),
         ("We design a solar-powered charging hub for a shared e-bike scheme at the "
          "University of Warwick, Coventry (CV4 7AL). The hub must stay affordable and "
          "reliable across every realistic future demand, not just an average forecast "
          "(Theme 3). We also model how the batteries charge and discharge on different "
          "routes and compare private versus shared e-bikes (Theme 2).", False)],
        [("Objectives. ", True),
         ("(1) build realistic demand scenarios for the scheme; (2) size the solar PV, "
          "battery and charge bays behind a limited grid connection; (3) measure the "
          "cost and service gained by designing for robustness; (4) test whether a "
          "battery is worth its cost.", False)],
        [("Research questions. ", True),
         ("How large should the hub be when demand is uncertain? What does robustness "
          "save against a normal average-demand design? Does a battery pay at a "
          "grid-connected hub? How do charge and discharge profiles differ between "
          "private and shared e-bikes?", False)],
        [("Methodology (Figure 1). ", True),
         ("We build Low, Medium and High demand scenarios from shared e-bike usage and "
          "scale them across a growth range into nine weighted scenarios; the loader "
          "reads the official UoW Bikes file directly when it is provided. A "
          "physics-based route model (Burani 2022; Ouf 2023) gives the energy each ride "
          "draws from gradient, speed, load and assist level, and produces the Theme 2 "
          "charge/discharge profiles. An hourly model over 8,760 hours sends solar to "
          "demand, then to the battery, then to the capped grid. We score all 150 "
          "designs (PV 5-25 kWp, battery 0-50 kWh, 4-20 bays) under five decision rules "
          "(naive, two-stage stochastic, CVaR, minimax-regret, maximin) and map the "
          "cost-versus-robustness frontier. We then test the result with a 500-run "
          "Monte-Carlo, Sobol sensitivity, a penalty-grid-horizon robustness sweep, and "
          "validation against published data. Solar (PVGIS, Coventry) and grid carbon "
          "(National Grid ESO, West Midlands) are real API data.", False)],
    ]

    outcomes = [
        [("Recommended design. ", True),
         (f"The model recommends {rec['pv_kwp']:g} kWp of solar, no battery, and "
          f"{rec['n_chargers']:g} smart-managed charge bays, costing about "
          f"£{capex:,.0f} (Figure 2).", False)],
        [("Value of robustness. ", True),
         (f"A normal design sized to average demand ({nai['pv_kwp']:g} kWp, "
          f"{nai['n_chargers']:g} bays) looks cheap but fails when demand is high: its "
          f"worst-case annual cost is £{vor['naive_worst_cost']:,.0f} and it serves only "
          f"{vor['naive_min_service']*100:.1f}% of charging. The robust design holds "
          f"worst-case cost to £{vor['robust_worst_cost']:,.0f}/yr, a "
          f"{vor['worst_cost_reduction_pct']:.0f}% (£{vor['worst_cost_reduction']:,.0f}) "
          f"cut, and keeps {vor['robust_min_service']*100:.1f}% service in every "
          f"scenario. This is not a strawman: the same search also produced stochastic "
          f"and CVaR designs, and the robust (maximin) design still gives the lowest "
          f"worst-case cost. Across the Monte-Carlo fan its 95th-percentile cost is "
          f"£{mc['robust']['cost_p95']:,.0f} against £{mc['naive']['cost_p95']:,.0f}, "
          f"roughly halving the downside. It beats the naive design in "
          f"{rob['fraction_robust_beats_naive_pct']:.0f}% of {rob['n_combinations']} "
          f"penalty-grid cases ({val} benchmarks validated).", False)],
        [("Does a battery pay? ", True),
         (f"Because charging is flexible, smart scheduling flattens the load below the "
          f"grid limit, so a battery never enters the robust design at the 15 kW "
          f"connection. A dedicated grid sweep shows a battery only pays at {sb_txt} "
          f"(toward off-grid). The greenest and cheapest answer is solar plus smart "
          f"bays, which also avoids the embodied carbon of an unneeded battery.", False)],
        [("Theme 2: routes and profiles (Figure 3). ", True),
         (f"The route model gives {t2.get('wh_per_km_grid_min',4):.0f}-"
          f"{t2.get('wh_per_km_grid_max',18):.0f} Wh/km depending on gradient, speed and "
          f"load (campus hops lowest, hilly and cargo trips highest). The profiles "
          f"differ clearly: a private e-bike makes two longer trips and takes one deep "
          f"overnight home charge ({p_efc:.0f} full cycles/yr), while a shared bike runs "
          f"many short trips, discharges deeper and is topped up at the depot "
          f"({s_efc:.0f} cycles/yr). Shared batteries work about {ratio:.1f}x harder and "
          f"age faster, which is why a shared scheme needs the managed hub and long-life "
          f"LFP cells.", False)],
        [("Sustainability. ", True),
         (f"The hub avoids {emis['carbon_saving_tCO2_yr']:.1f} tCO₂/yr, about "
          f"{emis['carbon_saving_pct']:.0f}% of grid-only emissions on a consequential "
          f"(marginal, gas-margin) basis, with {perf['solar_fraction_pct']:.0f}% of "
          f"demand met directly by solar. The LFP storage option (weak-grid case) is "
          f"cobalt and nickel free, with about 45% of pack mass recoverable.", False)],
        [("Output format (GUI). ", True),
         ("An interactive dashboard lets a planner set PV, battery, bays and the grid "
          "limit with sliders and see the hourly energy balance, service level, annual "
          "cost and carbon update live, alongside the Pareto frontier and Monte-Carlo "
          "fan. One command also writes results.json, every figure and this summary.", False)],
        [("Originality & reproducibility. ", True),
         ("All code was written for this project. Every number is reproducible from one "
          "command with a fixed seed and an automated test suite. Solar and grid carbon "
          "are real API data; demand is modelled from published shared e-bike statistics, "
          "validated against benchmarks, and replaced by the official UoW Bikes file when "
          "supplied.", False)],
    ]

    references = [
        "Burani, E., Cabri, G., Leoncini, M. (2022). An Algorithm to Predict E-Bike Power Consumption Based on Planned Routes. Electronics, 11(7), 1105.",
        "Ouf, K., Soubra, H., Mazhr, A. (2023). E-Bike Energy Needs Estimation based on Route Characteristics and Rider Behavior. IEEE ICICIS 2023, 345–352.",
        "Corti, F. et al. (2024). A comprehensive review of charging infrastructure for Electric Micromobility Vehicles. Energy Reports, 12, 545–567.",
        "Marie, J.-J. (2023). The Micromobility Revolution Gathers Momentum. Faraday Insights, Issue 16.",
        "Gössling, S. (2020). Integrating e-scooters in urban transportation. Transportation Research Part D, 79, 102230.",
        "Rockafellar, R.T., Uryasev, S. (2000). Optimization of Conditional Value-at-Risk. Journal of Risk, 2(3), 21–41.",
        "Birge, J.R., Louveaux, F. (2011). Introduction to Stochastic Programming, 2nd ed. Springer.",
        "PVGIS (EU JRC) hourly series, University of Warwick (52.3838, −1.5616); National Grid ESO Carbon Intensity API, West Midlands (region 8).",
        "Cost & performance benchmarks: BEIS, IRENA, BloombergNEF, IEA PVPS, Fraunhofer ISE — see REFERENCES.md.",
    ]

    github = (f"GitHub (executable code + README / QuickStart guide): {GITHUB_URL}  "
              "— the README documents the one-command run (“python run_analysis.py”), "
              "data sources and how to drop in the official UoW Bikes Data(Sheet1).csv.")

    return {"approach": approach, "outcomes": outcomes,
            "references": references, "github": github}


def _wordcount(blocks) -> int:
    text = " ".join(seg[0] for para in blocks for seg in para)
    return len(re.findall(r"\b[\w’'-]+\b", text))


# --------------------------------------------------------------------------- #
#  DOCX renderer (authoritative — Aptos 11 pt)
# --------------------------------------------------------------------------- #
def render_docx(c: dict, path: Path):
    from docx import Document
    from docx.shared import Pt, Mm, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    NAVY = RGBColor(0x1B, 0x1B, 0x3A)
    BLUE = RGBColor(0x2E, 0x86, 0xAB)
    GREY = RGBColor(0x55, 0x55, 0x60)
    FONT = "Aptos"

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    # ensure East-Asian/HAnsi slots also map to Aptos
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts"); rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(a), FONT)

    sec = doc.sections[0]
    sec.page_width = Mm(210); sec.page_height = Mm(297)
    sec.top_margin = Mm(25.4); sec.bottom_margin = Mm(25.4)
    sec.left_margin = Mm(25.4); sec.right_margin = Mm(25.4)

    def _set_font(run, size=11, bold=False, italic=False, color=None):
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        if color:
            run.font.color.rgb = color
        r = run._element.get_or_add_rPr()
        rf = r.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts"); r.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs"):
            rf.set(qn(a), FONT)

    def p(before=0, after=3, align=None, line=1.0):
        par = doc.add_paragraph()
        par.paragraph_format.space_before = Pt(before)
        par.paragraph_format.space_after = Pt(after)
        par.paragraph_format.line_spacing = line
        if align:
            par.alignment = align
        return par

    def heading(text):
        par = p(before=4, after=1)
        _set_font(par.add_run(text), size=13, bold=True, color=NAVY)
        # thin rule under the heading
        ppr = par._p.get_or_add_pPr()
        pbdr = OxmlElement("w:pBdr"); bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "2"); bottom.set(qn("w:color"), "C7D3DC")
        pbdr.append(bottom); ppr.append(pbdr)

    def body(runs):
        par = p(after=2, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        for text, bold in runs:
            _set_font(par.add_run(text), size=11, bold=bold)

    # --- header --------------------------------------------------------------
    tp = p(after=2, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(tp.add_run(f"Team Name: {TEAM_NAME}"), size=11, bold=True, color=GREY)
    ttl = p(after=1, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(ttl.add_run(TITLE), size=15, bold=True, color=NAVY)
    sub = p(after=4, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(sub.add_run(SUBTITLE), size=9.5, italic=True, color=BLUE)

    # --- Approach ------------------------------------------------------------
    heading(f"Approach  ({_wordcount(c['approach'])} words)")
    for runs in c["approach"]:
        body(runs)
    doc.add_picture(str(OUT / "methodology_flow.png"), width=Inches(4.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = p(after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_font(cap.add_run("Figure 1 — End-to-end methodology / algorithm flow."),
              size=8.5, italic=True, color=GREY)

    # --- Outcomes ------------------------------------------------------------
    heading(f"Outcomes  ({_wordcount(c['outcomes'])} words)")
    for runs in c["outcomes"]:
        body(runs)

    # results: compact 2-up (Pareto frontier + robustness-of-robustness)
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl = t._tbl
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "none"); borders.append(e)
    tbl.tblPr.append(borders)
    for i, img in enumerate(["02_pareto.png", "13b_route_soc.png"]):
        cell = t.rows[0].cells[i]; cell.width = Mm(80)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.paragraphs[0].add_run().add_picture(str(OUT / img), width=Inches(2.75))
    cap = p(after=3, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_font(cap.add_run("Figure 2 — Cost-vs-robustness Pareto frontier (Theme 3).   "
                          "Figure 3 — Personal vs shared e-bike charge/discharge profiles (Theme 2)."),
              size=8.5, italic=True, color=GREY)

    # --- GitHub --------------------------------------------------------------
    heading("Links to GitHub files")
    ghp = p(after=4, align=WD_ALIGN_PARAGRAPH.LEFT)
    _set_font(ghp.add_run(c["github"]), size=11, bold=False)

    # --- References ----------------------------------------------------------
    heading("References  (not counted in the word limit)")
    for i, ref in enumerate(c["references"], 1):
        par = p(after=1, line=1.0)
        _set_font(par.add_run(f"[{i}] {ref}"), size=7.6, color=GREY)

    doc.save(str(path))


# --------------------------------------------------------------------------- #
#  PDF renderer (backup — reportlab, Calibri stand-in for Aptos)
# --------------------------------------------------------------------------- #
def render_pdf(c: dict, path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                    Table, TableStyle, KeepTogether)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    fonts = Path("C:/Windows/Fonts")
    base, bold = "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("Body", str(fonts / "calibri.ttf")))
        pdfmetrics.registerFont(TTFont("Body-Bold", str(fonts / "calibrib.ttf")))
        base, bold = "Body", "Body-Bold"
    except Exception:
        pass

    NAVY = colors.HexColor("#1B1B3A"); BLUE = colors.HexColor("#2E86AB")
    GREY = colors.HexColor("#555560")

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def to_markup(runs):
        out = ""
        for text, b in runs:
            t = esc(text)
            out += f"<b>{t}</b>" if b else t
        return out

    body_st = ParagraphStyle("body", fontName=base, fontSize=11, leading=12.2,
                             alignment=4, spaceAfter=2, textColor=colors.HexColor("#1a1a1a"))
    h_st = ParagraphStyle("h", fontName=bold, fontSize=13, leading=15, textColor=NAVY,
                          spaceBefore=4, spaceAfter=2)
    team_st = ParagraphStyle("team", fontName=bold, fontSize=11, textColor=GREY, spaceAfter=2)
    title_st = ParagraphStyle("title", fontName=bold, fontSize=15, leading=18,
                              textColor=NAVY, spaceAfter=2)
    sub_st = ParagraphStyle("sub", fontName=base, fontSize=9.5, leading=12,
                            textColor=BLUE, spaceAfter=4)
    cap_st = ParagraphStyle("cap", fontName=base, fontSize=8.5, leading=10,
                            textColor=GREY, alignment=1, spaceAfter=3)
    ref_st = ParagraphStyle("ref", fontName=base, fontSize=7.6, leading=9,
                            textColor=GREY, spaceAfter=1)
    body_left = ParagraphStyle("bl", parent=body_st, alignment=0)

    def img_scaled(p, max_w):
        ir = ImageReader(str(p)); iw, ih = ir.getSize()
        w = max_w; h = w * ih / iw
        return Image(str(p), width=w, height=h)

    avail = A4[0] - 2 * 25.4 * mm
    story = [
        Paragraph(f"Team Name: {esc(TEAM_NAME)}", team_st),
        Paragraph(esc(TITLE), title_st),
        Paragraph(esc(SUBTITLE), sub_st),
        Paragraph(f"Approach&nbsp;&nbsp;({_wordcount(c['approach'])} words)", h_st),
    ]
    for runs in c["approach"]:
        story.append(Paragraph(to_markup(runs), body_st))
    story += [img_scaled(OUT / "methodology_flow.png", avail * 0.62),
              Paragraph("Figure 1 — End-to-end methodology / algorithm flow.", cap_st),
              Paragraph(f"Outcomes&nbsp;&nbsp;({_wordcount(c['outcomes'])} words)", h_st)]
    for runs in c["outcomes"]:
        story.append(Paragraph(to_markup(runs), body_st))
    half = avail * 0.49
    row = [[img_scaled(OUT / "02_pareto.png", half * 0.90),
            img_scaled(OUT / "13b_route_soc.png", half * 0.90)]]
    tbl = Table(row, colWidths=[avail * 0.5, avail * 0.5])
    tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                             ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [tbl,
              Paragraph("Figure 2 — Cost-vs-robustness Pareto frontier (Theme 3).   "
                        "Figure 3 — Personal vs shared e-bike charge/discharge profiles (Theme 2).", cap_st),
              Paragraph("Links to GitHub files", h_st),
              Paragraph(to_markup([(c["github"], False)]), body_left),
              Paragraph("References&nbsp;&nbsp;(not counted in the word limit)", h_st)]
    for i, ref in enumerate(c["references"], 1):
        story.append(Paragraph(f"[{i}] {esc(ref)}", ref_st))

    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=25.4 * mm, bottomMargin=25.4 * mm,
                            leftMargin=25.4 * mm, rightMargin=25.4 * mm,
                            title="Executive Summary")
    doc.build(story)


def build():
    c = _content()
    aw, ow = _wordcount(c["approach"]), _wordcount(c["outcomes"])
    docx_path = OUT / "Executive_Summary.docx"
    pdf_path = OUT / "Executive_Summary.pdf"
    render_docx(c, docx_path)
    try:
        render_pdf(c, pdf_path)
        pdf_msg = f" + {pdf_path.name}"
    except Exception as e:
        pdf_msg = f"  (PDF skipped: {str(e)[:70]})"
    print(f"Executive summary saved: {docx_path.name}{pdf_msg}")
    print(f"  Approach: {aw}/300 words | Outcomes: {ow}/500 words")
    if aw > 300 or ow > 500:
        print("  WARNING: a section exceeds its word limit — trim the content.")
    return docx_path


if __name__ == "__main__":
    build()
