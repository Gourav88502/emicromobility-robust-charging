"""
make_flow_diagram.py
====================
Renders the methodology flow diagram (outputs/methodology_flow.png) used in the
executive summary and README — the "Approach / algorithm" deliverable.
"""

from __future__ import annotations
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

C = {"data": "#2E86AB", "demand": "#F8961E", "core": "#1B1B3A",
     "robust": "#43AA8B", "side": "#577590", "out": "#E03616"}


def box(ax, x, y, w, h, text, color, tcolor="white", fs=10.5, bold=True):
    ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.08",
                 linewidth=0, facecolor=color, alpha=0.95, zorder=2))
    ax.text(x, y, text, ha="center", va="center", color=tcolor,
            fontsize=fs, fontweight="bold" if bold else "normal", zorder=3,
            family="DejaVu Sans", wrap=True)


def arrow(ax, x1, y1, x2, y2, color="#555", style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                 mutation_scale=16, linewidth=1.8, color=color, zorder=1))


def main():
    fig, ax = plt.subplots(figsize=(11, 8.2))
    ax.set_xlim(0, 12); ax.set_ylim(0, 13); ax.axis("off")

    ax.text(6, 12.5, "Methodology — Robust Solar Charging-Station Design",
            ha="center", fontsize=15, fontweight="bold", color=C["core"],
            family="DejaVu Sans")

    # Row 1: data inputs
    box(ax, 2.2, 11.2, 3.6, 0.9, "UoW Bikes e-bike demand\n(Low/Med/High)", C["data"], fs=9.5)
    box(ax, 6.0, 11.2, 3.2, 0.9, "PVGIS solar series\n(8,760 h, Coventry)", C["data"], fs=9.5)
    box(ax, 9.7, 11.2, 3.2, 0.9, "Carbon intensity\n(West Midlands grid)", C["data"], fs=9.5)

    # Row 2: scenarios
    box(ax, 6.0, 9.6, 8.6, 0.85,
        "3 usage levels x 5 growth paths  ->  15 probability-weighted futures", C["demand"],
        tcolor=C["core"], fs=10)
    arrow(ax, 2.2, 10.75, 3.2, 10.05)
    arrow(ax, 6.0, 10.75, 6.0, 10.05)
    arrow(ax, 9.7, 10.75, 8.8, 10.05)

    # Row 3: energy balance
    box(ax, 6.0, 8.0, 9.2, 0.95,
        f"Hourly energy-balance dispatch  (constrained {config.GRID_CONNECTION_KW:.0f} kW grid)\n"
        "PV -> battery -> capped grid -> unmet   ·   Numba-accelerated", C["core"], fs=10)
    arrow(ax, 6.0, 9.15, 6.0, 8.5)

    # Row 4: cost matrix
    box(ax, 6.0, 6.5, 9.2, 0.85,
        "Cost matrix: 150 candidate designs  x  15 weighted futures", C["side"], fs=10)
    arrow(ax, 6.0, 7.5, 6.0, 6.95)

    # Row 5: five decision rules (symmetric, fits within xlim 0-12)
    rules = [("Naive\n(determ.)", 1.4), ("Stochastic", 3.7), ("CVaR\n(tail-risk)", 6.0),
             ("Minimax\nregret", 8.3), ("Maximin\n(robust)", 10.6)]
    for txt, x in rules:
        col = C["robust"] if "Maximin" in txt else C["side"]
        box(ax, x, 5.0, 2.1, 0.95, txt, col, fs=8.5)
        arrow(ax, 6.0, 6.05, x, 5.5)

    # Row 6: outputs
    box(ax, 3.2, 3.4, 5.4, 0.95,
        "Recommended robust design\n+ Value of Robustness (cost & service)", C["robust"], fs=10)
    box(ax, 8.9, 3.4, 4.8, 0.95,
        "Cost-vs-robustness\nPareto frontier", C["out"], fs=10)
    for x in (1.4, 3.7, 6.0, 8.3, 10.6):
        arrow(ax, x, 4.5, 3.2 if x < 6.5 else 8.9, 3.9)

    # Side analyses
    box(ax, 3.2, 1.7, 5.4, 0.9, "Monte-Carlo fan (500 correlated samples)", C["demand"],
        tcolor=C["core"], fs=9.5)
    box(ax, 8.9, 1.7, 4.8, 0.9, "Tornado sensitivity (9 uncertainties)", C["demand"],
        tcolor=C["core"], fs=9.5)
    arrow(ax, 3.2, 2.9, 3.2, 2.15); arrow(ax, 8.9, 2.9, 8.9, 2.15)

    ax.text(6, 0.5, "Every stage is reproducible from one command (run_analysis.py); "
            "all assumptions traceable in config.py",
            ha="center", fontsize=8.5, style="italic", color="#667")

    out = config.OUTPUT_DIR / "methodology_flow.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Flow diagram saved: {out}")


if __name__ == "__main__":
    main()
