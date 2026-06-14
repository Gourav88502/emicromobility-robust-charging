"""
robustness.py
=============
Robustness-of-robustness: does the CONCLUSION ("a robust PV+storage+bays design
beats the naive average-demand design") survive changes to the three assumptions
a sceptic would attack — the unmet-demand penalty, the grid-connection limit, and
the design horizon?

For a grid of (penalty x grid-cap) and a sweep of horizons we re-run the whole
optimisation and record the value of robustness and the recommended design. If
the value of robustness stays positive and the recommendation stays stable across
the whole space, the headline is not an artefact of any single tuned number.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from . import config, demand_model, pv_model, optimization


def _run_once(designs, scenarios_cache, df, solar, horizon) -> dict:
    scen = scenarios_cache[horizon]
    cost, service = optimization.cost_matrix(designs, scen, solar)
    return optimization.solve(designs, scen, cost, service)


def sweep(df=None, solar=None,
          penalties=(2, 5, 10, 20, 40),
          grids=(6, 9, 12, 15, 18, 21, 24),
          horizons=(3, 4, 5, 6, 7)) -> dict:
    if df is None:
        df = demand_model.load_demand()
    if solar is None:
        solar = pv_model.load_solar()
    designs = optimization.all_designs()

    # save baseline config
    base_pen = config.UNMET_DEMAND_PENALTY
    base_grid = config.GRID_CONNECTION_KW
    base_hor = config.OPTIMISATION_HORIZON_YEARS

    # pre-build scenarios per horizon (demand doesn't depend on penalty/grid)
    scen_cache = {h: optimization.build_scenarios(df, h)
                  for h in set(horizons) | {base_hor}}

    # ---- (penalty x grid) grid at the baseline horizon --------------------- #
    vor = np.zeros((len(penalties), len(grids)))
    rec_pv = np.zeros_like(vor); rec_bess = np.zeros_like(vor)
    robust_beats_naive = np.zeros_like(vor, dtype=bool)
    for ip, pen in enumerate(penalties):
        for ig, g in enumerate(grids):
            config.UNMET_DEMAND_PENALTY = float(pen)
            config.GRID_CONNECTION_KW = float(g)
            r = _run_once(designs, scen_cache, df, solar, base_hor)
            v = r["value_of_robustness"]
            vor[ip, ig] = v["worst_cost_reduction_pct"]
            rec = r["rules"]["maximin_robust"]["design"]
            rec_pv[ip, ig] = rec.pv_kwp; rec_bess[ip, ig] = rec.battery_kwh
            robust_beats_naive[ip, ig] = v["worst_cost_reduction"] > 0

    # ---- horizon sweep at baseline penalty & grid -------------------------- #
    config.UNMET_DEMAND_PENALTY = base_pen
    config.GRID_CONNECTION_KW = base_grid
    hor_rows = []
    for h in horizons:
        r = _run_once(designs, scen_cache, df, solar, h)
        rec = r["rules"]["maximin_robust"]["design"]
        hor_rows.append({"horizon_years": h,
                         "value_of_robustness_pct": round(r["value_of_robustness"]["worst_cost_reduction_pct"], 1),
                         "recommended": str(rec),
                         "rec_pv_kwp": rec.pv_kwp, "rec_bess_kwh": rec.battery_kwh,
                         "rec_chargers": rec.n_chargers})

    # restore config
    config.UNMET_DEMAND_PENALTY = base_pen
    config.GRID_CONNECTION_KW = base_grid

    # Storage boundary: the LARGEST grid-connection level (kW) at which the typical
    # robust design (median over penalties) still includes a battery. Above it, a
    # grid-connected hub never benefits from storage; below it, storage enters.
    # This is what makes the "battery only pays toward off-grid" claim quantitative.
    med_bess = np.array([np.median(rec_bess[:, ig]) for ig in range(len(grids))])
    with_storage = [grids[ig] for ig in range(len(grids)) if med_bess[ig] > 0]
    storage_boundary = float(max(with_storage)) if with_storage else None

    return {
        "penalties": list(penalties), "grids": list(grids),
        "vor_pct": vor, "rec_pv": rec_pv, "rec_bess": rec_bess,
        "robust_beats_naive": robust_beats_naive,
        "horizon_table": pd.DataFrame(hor_rows),
        "fraction_robust_wins": float(robust_beats_naive.mean()),
        "vor_min": float(vor.min()), "vor_max": float(vor.max()),
        "vor_median": float(np.median(vor)),
        "storage_boundary_grid_kW": storage_boundary,
        "base_grid_kW": float(base_grid),
    }


def summary_text(res: dict) -> str:
    return (f"Robust beats naive in {res['fraction_robust_wins']*100:.0f}% of "
            f"{res['vor_pct'].size} (penalty x grid) combinations; value of "
            f"robustness ranges {res['vor_min']:.0f}-{res['vor_max']:.0f}% "
            f"(median {res['vor_median']:.0f}%).")


if __name__ == "__main__":
    import time
    t = time.time()
    res = sweep()
    print(f"Robustness-of-robustness sweep in {time.time()-t:.1f}s\n")
    print(summary_text(res))
    print("\nValue of robustness (%) over penalty (rows) x grid kW (cols):")
    hdr = "        " + "".join(f"{g:>6}" for g in res["grids"])
    print(hdr)
    for ip, pen in enumerate(res["penalties"]):
        print(f"  £{pen:>3}/kWh " + "".join(f"{res['vor_pct'][ip, ig]:>6.0f}"
                                            for ig in range(len(res["grids"]))))
    print("\nHorizon sweep:")
    print(res["horizon_table"].to_string(index=False))
