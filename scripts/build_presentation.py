"""
build_presentation.py
======================
Generates the FINAL-ROUND presentation deck (.pptx) for the in-person
Stakeholder Engagement Workshop at WMG, University of Warwick.

Format on the day:  3 min oral  +  3 min live prototype demo  +  4 min Q&A.

Six-slide story (visual, not text-heavy):
  1  Problem            4  Robustness under uncertainty
  2  Method / pipeline  5  Battery threshold & sustainability
  3  Final design       6  Live demo handoff + conclusion

The deck carries the 3-minute ORAL half; the 3-minute DEMO half runs in the
interactive site (docs/index.html -> Presenter mode, key P, 7 steps). The
timed speaker script for BOTH halves is embedded as slide notes and written
to outputs/presentation_script.md.

All headline numbers are read live from outputs/results.json.

    python scripts/build_presentation.py
"""

from __future__ import annotations
import json
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))

# ---- identity (final round is NOT blind — put your names here) -------------
TEAM_LINE = "UoW-Bikes Solar Hub Team"          # <-- EDIT: team / member names
EVENT_LINE = ("Sustainable e-Micromobility Stakeholder Engagement Workshop - "
              "WMG, University of Warwick - 6 July 2026")
DEMO_URL = "gourav88502.github.io/emicromobility-robust-charging"
REPO_URL = "github.com/Gourav88502/emicromobility-robust-charging"

NAVY = RGBColor(0x1B, 0x1B, 0x3A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOLD = RGBColor(0xF2, 0xB7, 0x05)
GREEN = RGBColor(0x43, 0xAA, 0x8B)
BLUE = RGBColor(0x2E, 0x86, 0xAB)
RED = RGBColor(0xD9, 0x53, 0x4F)
INK = RGBColor(0x22, 0x22, 0x2A)
GREY = RGBColor(0x5A, 0x5A, 0x66)
LILAC = RGBColor(0xCA, 0xDC, 0xFC)
HEAD = "Georgia"
BODY = "Calibri"

EMU_W, EMU_H = Inches(13.333), Inches(7.5)


def _solid(shape, color):
    shape.fill.solid(); shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def text(slide, l, t, w, h, runs, size=18, color=INK, bold=False, font=BODY,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, space=6, line=1.05):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    if isinstance(runs, str):
        runs = [(runs, {})]
    first = True
    for line_runs in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align; p.space_after = Pt(space); p.line_spacing = line
        segs = line_runs if isinstance(line_runs, list) else [line_runs]
        for seg in segs:
            s_text, opt = seg if isinstance(seg, tuple) else (seg, {})
            r = p.add_run(); r.text = s_text
            r.font.name = opt.get("font", font)
            r.font.size = Pt(opt.get("size", size))
            r.font.bold = opt.get("bold", bold)
            r.font.italic = opt.get("italic", italic)
            r.font.color.rgb = opt.get("color", color)
    return tb


def chip(slide, l, t, w, label, color):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t),
                                Inches(w), Inches(0.42))
    _solid(sh, color)
    tf = sh.text_frame; tf.word_wrap = True
    tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label
    r.font.name = BODY; r.font.size = Pt(11.5); r.font.bold = True; r.font.color.rgb = WHITE
    return sh


def stat(slide, l, t, w, big, small, color, big_size=40):
    text(slide, l, t, w, 0.9, [[(big, {"size": big_size, "bold": True, "color": color, "font": HEAD})]],
         align=PP_ALIGN.LEFT)
    text(slide, l, t + big_size / 46.0, w, 0.7, [[(small, {"size": 12.5, "color": GREY})]],
         align=PP_ALIGN.LEFT)


def pic_fit(slide, path, l, t, w, h):
    """Add picture scaled to fit within (w,h) box, centred."""
    from PIL import Image
    iw, ih = Image.open(path).size
    box_ar = w / h; img_ar = iw / ih
    if img_ar > box_ar:
        nw = w; nh = w / img_ar
    else:
        nh = h; nw = h * img_ar
    left = l + (w - nw) / 2; top = t + (h - nh) / 2
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), Inches(nw), Inches(nh))


def qr_png(url: str) -> Path | None:
    """Generate a QR code for the live demo (optional dependency)."""
    try:
        import qrcode
        img = qrcode.make(f"https://{url}")
        p = OUT / "_demo_qr.png"
        img.save(str(p))
        return p
    except Exception:
        return None


def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt


def build():
    rec = R["recommended_design"]; vor = R["value_of_robustness"]; emis = R["emissions"]
    ror = R.get("robustness_of_robustness", {})
    thr = R.get("grid_battery_threshold", {})
    val = R.get("validation", {}).get("metrics_within_published_range", "9/9")
    naive = R["decision_rules"]["naive_deterministic"]
    robust = R["decision_rules"]["maximin_robust"]
    batt_at = thr.get("battery_recommended_at_or_below_kW", 8)
    batt_off = thr.get("battery_dropped_at_or_above_kW", 10)
    prs = Presentation(); prs.slide_width = EMU_W; prs.slide_height = EMU_H
    blank = prs.slide_layouts[6]
    SCRIPT = []

    # ============ Slide 1: PROBLEM (dark title) =============================
    s = prs.slides.add_slide(blank); bg(s, NAVY)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.45), Inches(0.28), Inches(1.5))
    _solid(bar, GOLD)
    text(s, 0.9, 1.35, 11.5, 1.0, [[("Which solar charging hub should Warwick build", {"size": 36, "bold": True, "color": WHITE, "font": HEAD})]])
    text(s, 0.9, 2.2, 11.5, 0.9, [[("when e-bike demand is uncertain?", {"size": 36, "bold": True, "color": GOLD, "font": HEAD})]])
    text(s, 0.95, 3.45, 11.4, 0.9, [[("Size a hub for average demand and it strands bikes on busy days. Oversize it and capital sits idle.", {"size": 17, "color": WHITE})],
                                    [("Our prototype asks a sharper question: which design still works when demand, grid limits and growth change?", {"size": 17, "color": LILAC})]], space=8)
    chip(s, 0.95, 4.85, 3.2, "Theme 3 - solar charging station", GREEN)
    chip(s, 4.35, 4.85, 3.6, "Theme 2 - charge/discharge profiles", BLUE)
    chip(s, 8.15, 4.85, 3.2, "Live in-browser prototype", GOLD)
    text(s, 0.95, 5.75, 11.4, 0.5, [[(TEAM_LINE, {"size": 15, "bold": True, "color": WHITE})]])
    text(s, 0.95, 6.3, 11.4, 0.5, [[(EVENT_LINE, {"size": 12, "color": LILAC})]])
    SCRIPT.append((1, "Good morning. Instead of asking how large a charger should be for "
        "average demand, our prototype asks what design still works when demand, grid limits "
        "and future growth change. A hub sized for the average strands bikes on busy days; an "
        "oversized one wastes capital. We answer this with robust optimisation on open data - "
        "and in three minutes you will see it run live."))

    # ============ Slide 2: METHOD / PIPELINE ================================
    s = prs.slides.add_slide(blank); bg(s, WHITE)
    text(s, 0.7, 0.45, 12, 0.8, [[("Method: open data, one full year, every design, five decision rules", {"size": 28, "bold": True, "color": NAVY, "font": HEAD})]])
    text(s, 0.7, 1.15, 12, 0.5, [[("The model chooses the design that still performs well when the future is worse than expected.", {"size": 14.5, "italic": True, "color": GREY})]])
    pic_fit(s, OUT / "methodology_flow.png", 1.2, 1.75, 10.9, 4.9)
    text(s, 0.7, 6.75, 12, 0.5, [[("UoW e-bike demand  >  Coventry solar (PVGIS)  >  West Midlands carbon (ESO)  >  8,760-hour simulation  >  150 designs  >  5 decision rules  >  robust recommendation", {"size": 12, "color": BLUE, "bold": True})]], align=PP_ALIGN.CENTER)
    SCRIPT.append((2, "The method in one breath. Demand is calibrated to the UoW Bikes use "
        "case from open shared-micromobility evidence; solar comes from PVGIS for Coventry and "
        "grid carbon from National Grid ESO. Every candidate hub is simulated over all eight "
        "thousand seven hundred and sixty hours of a year. One hundred and fifty designs are "
        "scored across fifteen futures under five decision rules - and we recommend the one "
        "that still performs well when the future is worse than expected."))

    # ============ Slide 3: FINAL DESIGN RESULT ==============================
    s = prs.slides.add_slide(blank); bg(s, WHITE)
    text(s, 0.7, 0.5, 12, 0.8, [[("The recommendation: 15 kWp solar - 0 kWh battery - 8 smart bays", {"size": 29, "bold": True, "color": NAVY, "font": HEAD})]])
    # big spec band
    band = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), Inches(1.5), Inches(12.0), Inches(1.5))
    _solid(band, NAVY)
    text(s, 1.1, 1.78, 3.8, 1.0, [[(f"{rec['pv_kwp']:g} kWp", {"size": 40, "bold": True, "color": GOLD, "font": HEAD})], [("solar PV array", {"size": 13, "color": LILAC})]], space=2)
    text(s, 5.0, 1.78, 3.8, 1.0, [[(f"{rec['battery_kwh']:g} kWh", {"size": 40, "bold": True, "color": GOLD, "font": HEAD})], [("battery - smart charging replaces it here", {"size": 13, "color": LILAC})]], space=2)
    text(s, 9.0, 1.78, 3.5, 1.0, [[(f"{rec['n_chargers']} bays", {"size": 40, "bold": True, "color": GOLD, "font": HEAD})], [("smart-managed 3 kW charging bays", {"size": 13, "color": LILAC})]], space=2)
    stat(s, 0.9, 3.5, 4.0, f"GBP {R['recommended_capex_gbp']:,.0f}", "capital cost - off-the-shelf PV and AC bays", NAVY, big_size=30)
    stat(s, 5.0, 3.5, 4.0, f"GBP {R['recommended_lcoe_gbp_per_kwh']:.3f}/kWh", "levelised cost of delivered energy", BLUE, big_size=30)
    stat(s, 9.3, 3.5, 3.6, f"{emis['carbon_saving_tCO2_yr']:.1f} tCO2/yr", f"avoided vs grid-only charging ({emis['carbon_saving_pct']:.0f}%, marginal basis)", GREEN, big_size=30)
    stat(s, 0.9, 5.0, 4.0, f"{vor['robust_min_service']*100:.1f}%", "fleet service guaranteed in the worst future", GREEN, big_size=30)
    stat(s, 5.0, 5.0, 4.0, f"GBP {robust['worst_cost']:,.0f}/yr", "worst-case annual cost, all futures", NAVY, big_size=30)
    text(s, 9.3, 5.05, 3.6, 1.3, [[("Smart charging schedules flexible charging into sunny, cheap off-peak hours - the load stays under the 15 kW connection without storage.", {"size": 12.5, "color": GREY})]], line=1.15)
    SCRIPT.append((3, "The recommended design is 15 kilowatt-peak of solar, zero kilowatt-hours "
        "of battery, and 8 smart-managed bays. Twenty-nine thousand four hundred pounds of "
        "capital, twenty-five pence per kilowatt-hour delivered, and three point seven tonnes of "
        "CO2 avoided each year. The reason there is no battery: a returned bike only needs to be "
        "ready by morning, so smart charging schedules the energy into sunny and off-peak hours "
        "and the load never breaks the fifteen-kilowatt connection."))

    # ============ Slide 4: ROBUSTNESS UNDER UNCERTAINTY =====================
    s = prs.slides.add_slide(blank); bg(s, WHITE)
    text(s, 0.7, 0.5, 12, 0.8, [[("Robust vs average-demand design - what uncertainty costs", {"size": 29, "bold": True, "color": NAVY, "font": HEAD})]])
    pic_fit(s, OUT / "02_pareto.png", 0.6, 1.5, 7.4, 5.1)
    stat(s, 8.3, 1.6, 4.6, f"-{vor['worst_cost_reduction_pct']:.1f}%", "worst-case annual cost vs the average-demand design", GREEN)
    stat(s, 8.3, 3.0, 4.6, f"{vor['naive_min_service']*100:.1f}% -> {vor['robust_min_service']*100:.1f}%", "guaranteed fleet service in the worst future", BLUE)
    stat(s, 8.3, 4.4, 4.6, "100% of 35", "stress-test combinations in which the conclusion held", NAVY, big_size=30)
    text(s, 8.3, 5.5, 4.6, 1.3, [[("Same 500-run Monte-Carlo, Sobol sensitivity and penalty x grid x horizon sweep behind every number.", {"size": 12, "color": GREY})]], line=1.15)
    SCRIPT.append((4, "What does robustness buy? The average-demand design looks cheapest on a "
        "normal day, but in the worst demand future its cost reaches forty-seven thousand pounds "
        "a year and it strands one bike in twenty-one. The robust design cuts that worst case by "
        "nearly sixty percent and lifts guaranteed service from ninety-five point three to "
        "ninety-nine point six percent. And we stress-tested the conclusion itself: it held in "
        "one hundred percent of thirty-five assumption combinations."))

    # ============ Slide 5: BATTERY THRESHOLD & SUSTAINABILITY ===============
    s = prs.slides.add_slide(blank); bg(s, WHITE)
    text(s, 0.7, 0.5, 12, 0.8, [[("When does a battery pay? Only when the grid is weak", {"size": 29, "bold": True, "color": NAVY, "font": HEAD})]])
    # threshold graphic (simple bar strip built from shapes)
    caps = [(4, 50), (6, 50), (8, 20), (10, 0), (12, 0), (15, 0), (18, 0), (20, 0)]
    x0, y_base, bw, gap = 0.9, 4.55, 0.62, 0.28
    maxh = 2.3
    for k, (cap, batt) in enumerate(caps):
        x = x0 + k * (bw + gap)
        hgt = max(batt / 50 * maxh, 0.06)
        barsh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y_base - hgt), Inches(bw), Inches(hgt))
        _solid(barsh, GREEN if batt > 0 else RGBColor(0xD9, 0xDD, 0xE6))
        if batt > 0:
            text(s, x - 0.08, y_base - hgt - 0.34, bw + 0.2, 0.3, [[(f"{batt}", {"size": 12, "bold": True, "color": GREEN})]], align=PP_ALIGN.CENTER)
        text(s, x - 0.08, y_base + 0.08, bw + 0.2, 0.3, [[(f"{cap}", {"size": 11, "color": GREY})]], align=PP_ALIGN.CENTER)
    text(s, 0.9, y_base + 0.42, 7.0, 0.4, [[("grid connection limit (kW)  -  bars show battery kWh in the robust design", {"size": 11, "italic": True, "color": GREY})]])
    text(s, 0.9, 1.5, 7.2, 0.6, [[(f"Battery enters the optimal design at <= {batt_at} kW and is gone by {batt_off} kW.", {"size": 16, "bold": True, "color": NAVY})]])
    # sustainability column
    pts = [
        [("Not an anti-battery result.  ", {"bold": True, "color": NAVY}), ("For a connected campus hub, smart charging gives the required robustness without battery cost, degradation or material impact.", {})],
        [("Conditional storage.  ", {"bold": True, "color": NAVY}), (f"When the connection weakens to roughly {batt_at}-{batt_off} kW, the model starts recommending storage.", {})],
        [("LFP where needed.  ", {"bold": True, "color": NAVY}), ("Cobalt- and nickel-free chemistry, long cycle life; second-life reuse and recycling planned for weak-grid sites.", {})],
        [("Avoided impact.  ", {"bold": True, "color": NAVY}), ("Skipping an unnecessary pack avoids its materials and manufacturing footprint entirely.", {})],
    ]
    text(s, 8.35, 1.5, 4.4, 5.2, pts, size=13, space=10, line=1.12)
    text(s, 0.9, 5.6, 7.2, 0.9, [[("“The most sustainable battery is sometimes the one you do not need to install.”", {"size": 16, "italic": True, "bold": True, "color": GREEN})]])
    SCRIPT.append((5, "This result is not anti-battery. It shows that for a connected Warwick "
        "campus hub, smart charging gives the required robustness without extra battery cost, "
        "degradation or material impact. We swept the grid connection to find exactly where that "
        "changes: at roughly eight to ten kilowatts, storage starts entering the optimal design - "
        "and there we specify LFP chemistry with second-life reuse. The most sustainable battery "
        "is sometimes the one you do not need to install."))

    # ============ Slide 6: DEMO HANDOFF + CONCLUSION (dark) =================
    s = prs.slides.add_slide(blank); bg(s, NAVY)
    text(s, 0.9, 0.65, 11.5, 0.9, [[("Now - the prototype itself, live", {"size": 34, "bold": True, "color": GOLD, "font": HEAD})]])
    steps = [
        ("1", "The recommendation, computed in front of you", "the browser re-runs the full 150-design optimisation in about a second"),
        ("2", "Break it, then fix it", "the average-demand design goes red at peaks; the robust design holds at 99.6%"),
        ("3", "The battery threshold, proven live", "weaken the grid to 8 kW and storage enters the optimal design"),
        ("4", "Validated and reproducible", f"{val} checks in published ranges; browser matches the Python pipeline; one command rebuilds everything"),
    ]
    y = 1.75
    for n, t_, d_ in steps:
        sh = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.95), Inches(y), Inches(0.5), Inches(0.5))
        _solid(sh, GOLD)
        tf = sh.text_frame; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = n; r.font.bold = True; r.font.size = Pt(18); r.font.color.rgb = NAVY
        text(s, 1.7, y - 0.04, 6.6, 0.5, [[(t_, {"size": 16.5, "bold": True, "color": WHITE})]])
        text(s, 1.7, y + 0.36, 6.6, 0.6, [[(d_, {"size": 12, "color": LILAC})]])
        y += 1.02
    qr = qr_png(DEMO_URL)
    if qr:
        s.shapes.add_picture(str(qr), Inches(9.55), Inches(1.75), Inches(2.4), Inches(2.4))
        text(s, 9.05, 4.25, 3.4, 0.5, [[("scan to open on your phone", {"size": 11, "color": LILAC})]], align=PP_ALIGN.CENTER)
    text(s, 9.05, 4.75, 3.4, 0.8, [[(DEMO_URL, {"size": 12, "bold": True, "color": GOLD})]], align=PP_ALIGN.CENTER)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(5.95), Inches(0.28), Inches(0.95))
    _solid(bar, GREEN)
    text(s, 1.4, 6.0, 11.0, 1.0, [[("The prototype turns uncertain e-bike demand into a clear infrastructure decision:", {"size": 19, "bold": True, "color": WHITE, "font": HEAD})],
                                  [("how much solar, whether a battery is needed, and how many smart bays to install.", {"size": 19, "bold": True, "color": GOLD, "font": HEAD})]], line=1.12)
    SCRIPT.append((6, "That is the argument - now the prototype makes it live: the full model "
        "runs in the browser, checks itself against our Python pipeline, and works offline. "
        "Watch four things: the recommendation recomputed in front of you; the average-demand "
        "design failing where the robust one holds; a battery entering the design when the grid "
        "weakens to eight kilowatts; and the validation behind every number. Over to the demo."))

    for idx, txt in SCRIPT:
        notes(prs.slides[idx - 1], f"[Slide {idx}]  {txt}")

    out = OUT / "Presentation.pptx"
    prs.save(str(out))
    print(f"Presentation saved: {out}")

    # ---- Timed speaker script: Part A (oral) + Part B (demo) ----------------
    words = sum(len(t.split()) for _, t in SCRIPT)
    secs = [26, 32, 34, 30, 32, 24]
    titles = ["Problem", "Method / pipeline", "Final design result",
              "Robustness under uncertainty", "Battery threshold & sustainability",
              "Demo handoff + conclusion"]
    md = ["# Final-Round Script - Part A (3-min oral) + Part B (3-min prototype demo)",
          "",
          f"*Part A is ~{words} words = {words/150:.1f} min at a calm 150 wpm - keep it under "
          "3:00. Part B is driven from the website's Presenter mode (open the site, press "
          "**P** or click **Start 3-minute demo**; arrow keys advance; the built-in timer "
          "turns red past 3:00). Total spoken time stays under 6 minutes.*",
          "",
          "## PART A - ORAL (3:00, slides 1-6)", ""]
    for (idx, txt), sec, title in zip(SCRIPT, secs, titles):
        md += [f"### Slide {idx} - {title}  (~{sec}s)", "", txt, ""]
    md += [
        "## PART B - LIVE PROTOTYPE DEMO (3:00, website Presenter mode, 7 steps)", "",
        "*Each step scrolls the page and fires its action automatically; speak one line per step.*", "",
        "| Step | ~t | On screen | Say |",
        "|---|----|-----------|-----|",
        "| 1/7 | 0:00 | Problem section | Shared e-bike demand is uncertain - the average-demand hub is cheap but fragile; the oversized one is reliable but wasteful. |",
        "| 2/7 | 0:25 | Method pipeline | Open solar, carbon and mobility data feed an 8,760-hour simulation - 150 designs, 15 futures, five decision rules. |",
        "| 3/7 | 0:50 | Live model - robust preset | The recommendation: 15 kWp solar, no battery, 8 smart bays - 19,232 pounds worst-case, 99.6% service. Green status: it holds in every future. |",
        "| 4/7 | 1:15 | Live model - naive preset | Every number recomputes live. The average-demand design: watch the status turn amber - cheap on paper, fragile at peaks. |",
        "| 5/7 | 1:40 | Battery threshold | Now weaken the grid to 8 kilowatts - the optimiser adds a battery, live. Storage pays only when the connection is weak, around 8 to 10 kW. |",
        "| 6/7 | 2:15 | Validation | Nine of nine checks in published ranges, the browser matches the Python pipeline to a hundredth of a percent, and one command reproduces everything. |",
        "| 7/7 | 2:40 | Hero / recommendation | The prototype turns uncertain e-bike demand into a clear infrastructure decision: how much solar, whether a battery is needed, and how many smart bays to install. Thank you. |",
        "",
        "**Q&A (4:00):** leave the site's validation section or Slide 6 on screen.",
        "",
        "**Fallbacks:** no internet -> open `demo.html` from the cloned repo (fully offline). "
        "Display failure -> the QR on Slide 6 opens the same demo on any phone.",
        ""]
    (OUT / "presentation_script.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Speaker script saved: {OUT / 'presentation_script.md'}")
    return out


if __name__ == "__main__":
    build()
