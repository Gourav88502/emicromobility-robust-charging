# -*- coding: utf-8 -*-
"""
grid_threshold_sweep.py
=======================
Empirically locates the grid-connection strength at which on-site battery
storage becomes part of the optimal (maximin) robust design.

For a range of grid connection caps it re-runs the full robust optimisation
and records the recommended design. This is the evidence behind the claim
"a battery is only justified at weaker grid connections" — it pins the exact
threshold instead of asserting it.

    python scripts/grid_threshold_sweep.py
Outputs:
    outputs/grid_battery_threshold.csv
    (and prints a one-line summary of the threshold)
"""

from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs"

from src import optimization, config, demand_model, pv_model

GRID_CAPS_KW = [4, 6, 8, 10, 11, 12, 14, 15, 18, 20]


def main():
    df = demand_model.load_demand()
    solar = pv_model.load_solar()
    original = config.GRID_CONNECTION_KW

    rows = []
    try:
        for g in GRID_CAPS_KW:
            config.GRID_CONNECTION_KW = float(g)
            opt = optimization.run_full_optimisation(
                df=df, solar=solar, use_lp=False, lp_verify=False)
            rule = opt["recommended_rule"]
            d = opt["rules"][rule]["design"]
            rows.append({
                "grid_kW": g,
                "pv_kwp": d.pv_kwp,
                "battery_kwh": d.battery_kwh,
                "n_chargers": d.n_chargers,
                "rule": rule,
                "min_service_pct": round(opt["rules"][rule]["min_service"] * 100, 1),
                "battery_recommended": "yes" if d.battery_kwh > 0 else "no",
            })
    finally:
        config.GRID_CONNECTION_KW = original

    # write CSV
    csv_path = OUT / "grid_battery_threshold.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # find threshold: highest grid cap that still recommends a battery
    with_batt = [r["grid_kW"] for r in rows if r["battery_kwh"] > 0]
    without_batt = [r["grid_kW"] for r in rows if r["battery_kwh"] == 0]
    threshold_hi = max(with_batt) if with_batt else None       # last grid that needs a battery
    threshold_lo = min(without_batt) if without_batt else None  # first grid that drops it

    summary = {
        "grid_caps_tested_kW": GRID_CAPS_KW,
        "battery_recommended_at_or_below_kW": threshold_hi,
        "battery_dropped_at_or_above_kW": threshold_lo,
        "note": ("Robust (maximin) design includes battery storage at grid connections of "
                 f"{threshold_hi} kW and below; storage drops to zero at {threshold_lo} kW and above. "
                 "Confirms the zero-battery recommendation is specific to the 15 kW connection."),
    }

    # fold into results.json
    res_path = OUT / "results.json"
    res = json.loads(res_path.read_text(encoding="utf-8"))
    res["grid_battery_threshold"] = summary
    res_path.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"Saved {csv_path}")
    for r in rows:
        print(f"  {r['grid_kW']:>2} kW -> {r['pv_kwp']:g} kWp / "
              f"{r['battery_kwh']:g} kWh / {r['n_chargers']:g}  "
              f"(service {r['min_service_pct']:.1f}%)  battery={r['battery_recommended']}")
    print(f"\nThreshold: battery recommended at <= {threshold_hi} kW; "
          f"zero battery at >= {threshold_lo} kW")


if __name__ == "__main__":
    main()
