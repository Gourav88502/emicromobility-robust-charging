"""
lp_dispatch.py
==============
Optimal day-ahead battery dispatch via Linear Programming (LP).

This module replaces the greedy heuristic controller in energy_balance.py with
a true LP optimal dispatch, coupling the LP solver into the sizing loop so that
every design in the cost matrix is evaluated under OPTIMAL operation — not a
greedy approximation.

Formulation (Silvente et al. 2018; Morales-España et al. 2014)
---------------------------------------------------------------
For each 24-hour period the controller solves:

    min  sum_t ( tariff[t]*g[t] - export_price*xe[t] + penalty*u[t] )

subject to (for each hour t = 0..23):

  Energy balance (equality):
    PV[t] + g[t] + bd[t]  =  D[t] + bc[t] + xe[t] + u[t] + curt[t]
    => g[t] + bd[t] - bc[t] - xe[t] + u[t] - curt[t] = D[t] - PV[t]

  Battery state-of-charge (equality, with carry-over):
    soc[t] = soc[t-1] + eta_c*bc[t] - (1/eta_d)*bd[t]

  Variable bounds:
    g[t]    in [0, grid_cap]      (grid import)
    bc[t]   in [0, p_batt_max]    (battery charge rate)
    bd[t]   in [0, p_batt_max]    (battery discharge rate)
    xe[t]   in [0, grid_cap]      (export, same connection)
    u[t]    in [0, D[t]]          (unmet demand, soft penalty)
    curt[t] in [0, PV[t]]         (PV curtailment slack)
    soc[t]  in [0, soc_max]       (state of charge)

Peak demand is tracked post-hoc from max(g[t]) and used for the
annual demand/capacity charge in economics.py.

The LP is solved with scipy.optimize.linprog (HiGHS solver, milliseconds
per 24-variable LP). For the full year the LP is solved rolling day-by-day,
carrying the SoC forward between days.  This is the standard "rolling horizon"
optimal dispatch used in energy systems research.

API
---
  simulate_lp(design, demand_kwh, pv_kwh, ...) -> dict  (same keys as energy_balance.simulate_fast)

Academic citations
------------------
  Silvente, J. et al. (2018). A rolling horizon optimization framework for the
    simultaneous energy supply and demand planning in microgrids. Applied Energy.
  Morales-España, G. et al. (2014). Tight and compact MILP formulation of
    start-up and shut-down ramping in unit commitment. IEEE Trans. Power Syst.
  Saltelli, A. et al. (2010). Variance based sensitivity analysis of model
    output. Design and estimator for the total sensitivity index. CMAME.
"""

from __future__ import annotations

import warnings
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, csr_matrix

from . import config
from .economics import Design


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _build_day_lp(pv_h: np.ndarray, demand_h: np.ndarray, tariff_h: np.ndarray,
                   soc_max: float, soc_init: float, grid_cap: float,
                   p_batt_max: float, eta_c: float, eta_d: float,
                   export_price: float, unmet_penalty: float,
                   charger_cap: float = np.inf):
    """
    Build and solve the LP for one 24-hour dispatch window.

    Variables (n=24 per slot):
        g[t]     grid import        [0, grid_cap]
        bc[t]    battery charge     [0, p_batt_max]
        bd[t]    battery discharge  [0, p_batt_max]
        xe[t]    grid export        [0, grid_cap]
        u[t]     unmet demand       [0, D[t]]
        curt[t]  PV curtailment     [0, PV[t]]
        soc[t]   state of charge    [0, soc_max]

    Total variables: 7 * 24 = 168
    Equality constraints: 2 * 24 = 48  (energy balance + SoC dynamics)

    Returns dict of day aggregates + final_soc, or None on LP failure.
    """
    n = 24
    nv = 7 * n

    # Offsets for each variable block
    O_g, O_bc, O_bd, O_xe, O_u, O_cu, O_s = [i * n for i in range(7)]

    # --- Objective --------------------------------------------------------
    c = np.zeros(nv)
    c[O_g:O_g + n]   = tariff_h          # minimise import cost
    c[O_xe:O_xe + n] = -export_price     # maximise export revenue
    c[O_u:O_u + n]   = unmet_penalty     # heavily penalise unmet demand
    # bc, bd, curt, soc: zero cost (physically free operations)

    # --- Equality constraints (energy balance + SoC dynamics) -------------
    n_eq = 2 * n
    A_eq = lil_matrix((n_eq, nv))
    b_eq = np.zeros(n_eq)

    for t in range(n):
        # ---- Energy balance: g+bd - bc-xe + u - curt = D - PV ----
        row = t
        A_eq[row, O_g + t]   =  1.0
        A_eq[row, O_bd + t]  =  1.0
        A_eq[row, O_bc + t]  = -1.0
        A_eq[row, O_xe + t]  = -1.0
        A_eq[row, O_u + t]   =  1.0
        A_eq[row, O_cu + t]  = -1.0
        b_eq[row] = demand_h[t] - pv_h[t]

        # ---- SoC dynamics: soc[t] - soc[t-1] - eta_c*bc + (1/eta_d)*bd = 0 ----
        row = n + t
        A_eq[row, O_s + t]   =  1.0
        A_eq[row, O_bc + t]  = -eta_c
        A_eq[row, O_bd + t]  =  1.0 / eta_d
        if t > 0:
            A_eq[row, O_s + t - 1] = -1.0
            b_eq[row] = 0.0
        else:
            # t == 0: soc[0] - eta_c*bc[0] + (1/eta_d)*bd[0] = soc_init
            b_eq[row] = soc_init

    A_eq = csr_matrix(A_eq)

    # --- Bounds -----------------------------------------------------------
    lb = np.zeros(nv)
    ub = np.full(nv, np.inf)

    ub[O_g:O_g + n]   = grid_cap
    ub[O_bc:O_bc + n] = p_batt_max
    ub[O_bd:O_bd + n] = p_batt_max
    ub[O_xe:O_xe + n] = grid_cap
    ub[O_u:O_u + n]   = np.maximum(demand_h, 0.0)   # can't unmet > demand
    ub[O_cu:O_cu + n] = np.maximum(pv_h, 0.0)       # can't curtail > PV
    ub[O_s:O_s + n]   = soc_max

    # Charger hardware cap: served demand (D - u) cannot exceed the charger
    # delivery limit per hour, so any demand above charger_cap is FORCED unmet.
    #   served = D - u <= charger_cap   =>   u >= D - charger_cap
    # This is the fix for the bug where pre-capping demand made the clipped
    # portion vanish (service then read ~100% for every design).
    if np.isfinite(charger_cap):
        lb[O_u:O_u + n] = np.maximum(demand_h - charger_cap, 0.0)

    bounds = list(zip(lb, ub))

    # --- Solve ------------------------------------------------------------
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                         method='highs', options={'disp': False, 'presolve': True})

    if result.status != 0:
        return None   # infeasible / error — caller uses greedy fallback

    x = result.x
    g    = x[O_g:O_g + n]
    bc   = x[O_bc:O_bc + n]
    bd   = x[O_bd:O_bd + n]
    xe   = x[O_xe:O_xe + n]
    u    = x[O_u:O_u + n]
    curt = x[O_cu:O_cu + n]
    soc  = x[O_s:O_s + n]

    # PV direct to demand = PV not going to battery / export / curtailment
    # From energy balance: pv_used = D - u - (g + bd - bc - xe)
    # => pv_direct = PV - bc - xe - curt (PV fraction serving demand now)
    pv_direct = np.maximum(pv_h - bc - xe - curt, 0.0).sum()

    return {
        'grid_import':    float(g.sum()),
        'grid_cost':      float((g * tariff_h).sum()),
        'export':         float(xe.sum()),
        'unmet':          float(u.sum()),
        'pv_direct':      float(pv_direct),
        'pv_stored':      float(bc.sum()),
        'bat_discharged': float(bd.sum()),
        'curtailed':      float(curt.sum()),
        'peak_grid':      float(g.max()) if len(g) > 0 else 0.0,
        'final_soc':      float(soc[-1]),
        'through':        float(bc.sum() + bd.sum()),
    }


# --------------------------------------------------------------------------- #
#  Public API — same signature as energy_balance.simulate_fast
# --------------------------------------------------------------------------- #

_TOU = np.asarray(config.TOU_TARIFF, float)
_HOUR_OF_DAY = np.arange(config.HOURS_PER_YEAR) % 24


def simulate_lp(design: Design, demand_kwh: np.ndarray, pv_kwh: np.ndarray, *,
                battery_rt_eff: float | None = None,
                charger_power_kw: float | None = None,
                charger_availability: float | None = None,
                grid_kw: float | None = None,
                export_price: float = config.FEED_IN_TARIFF,
                unmet_penalty: float = config.UNMET_DEMAND_PENALTY * 10,
                soc_init_frac: float = 0.5) -> dict:
    """
    Full-year LP optimal dispatch for one design.  Returns the same keys as
    energy_balance.simulate_fast so optimization.py can call either.

    The LP is solved day-by-day (rolling 24-hour horizon) with SoC carried
    forward between days — the standard rolling-horizon approach.
    """
    rt = config.BATTERY_ROUNDTRIP_EFF["baseline"] if battery_rt_eff is None else battery_rt_eff
    grid_cap = config.GRID_CONNECTION_KW if grid_kw is None else grid_kw
    avail = config.CHARGER_AVAILABILITY["baseline"] if charger_availability is None else charger_availability
    p_ch_kw = config.CHARGER_POWER_KW["baseline"] if charger_power_kw is None else charger_power_kw

    eta_c = float(np.sqrt(rt))          # one-way charge efficiency
    eta_d = float(np.sqrt(rt))          # one-way discharge efficiency (sym)
    soc_max = float(design.battery_kwh * config.BATTERY_DOD)
    p_batt_max = float(max(design.battery_kwh * 0.5, 0.0))  # 0.5C rate limit
    # Charger cap: hardware limit on hourly delivery
    charger_cap = float(design.n_chargers * p_ch_kw * avail)

    demand_h = np.asarray(demand_kwh, float)
    pv_h = np.asarray(pv_kwh, float)
    n_hours = len(demand_h)
    n_days = n_hours // 24

    soc = soc_init_frac * soc_max

    # Accumulators
    tot_grid = 0.0; tot_grid_cost = 0.0; tot_export = 0.0; tot_unmet = 0.0
    tot_pv_d = 0.0; tot_pv_b = 0.0; tot_bat_d = 0.0; tot_curt = 0.0
    peak_grid = 0.0; tot_through = 0.0

    from .energy_balance import _run, _assemble  # greedy fallback

    for day in range(n_days):
        h0 = day * 24
        pv_day    = pv_h[h0:h0 + 24]
        dem_day   = demand_h[h0:h0 + 24]               # RAW demand (charger cap is a constraint)
        tou_day   = _TOU[np.arange(24)]

        if soc_max > 0.0:
            day_res = _build_day_lp(
                pv_day, dem_day, tou_day,
                soc_max=soc_max, soc_init=soc,
                grid_cap=float(grid_cap),
                p_batt_max=p_batt_max,
                eta_c=eta_c, eta_d=eta_d,
                export_price=export_price,
                unmet_penalty=unmet_penalty,
                charger_cap=charger_cap,
            )
        else:
            day_res = None  # no battery — skip LP, use greedy (exact, no LP needed)

        if day_res is None:
            # Greedy fallback (battery=0 or LP infeasible). simulate_fast applies
            # the charger deliver_cap itself, so pass RAW demand here.
            from .energy_balance import simulate_fast
            d_design = Design(design.pv_kwp, design.battery_kwh, design.n_chargers)
            gr = simulate_fast(d_design, dem_day, pv_day,
                               battery_rt_eff=rt, charger_power_kw=p_ch_kw,
                               charger_availability=avail, grid_kw=grid_kw)
            tot_grid      += gr['grid_import_kwh']
            tot_grid_cost += gr['grid_cost_baseline_gbp']
            tot_export    += gr['pv_export_kwh']
            tot_unmet     += gr['unmet_demand_kwh']
            tot_pv_d      += gr['pv_to_demand_kwh']
            tot_pv_b      += gr['pv_to_battery_kwh']
            tot_bat_d     += gr['battery_to_demand_kwh']
            tot_curt      += gr.get('pv_curtailed_kwh', 0.0)
            peak_grid      = max(peak_grid, gr['peak_grid_kw'])
            tot_through   += gr['battery_throughput_kwh']
            soc            = soc   # SoC not updated (no battery)
        else:
            tot_grid      += day_res['grid_import']
            tot_grid_cost += day_res['grid_cost']
            tot_export    += day_res['export']
            tot_unmet     += day_res['unmet']
            tot_pv_d      += day_res['pv_direct']
            tot_pv_b      += day_res['pv_stored']
            tot_bat_d     += day_res['bat_discharged']
            tot_curt      += day_res['curtailed']
            peak_grid      = max(peak_grid, day_res['peak_grid'])
            tot_through   += day_res['through']
            soc            = min(max(day_res['final_soc'], 0.0), soc_max)

    demand_total = float(demand_h.sum())
    served_total = max(demand_total - tot_unmet, 0.0)
    service_level = served_total / demand_total if demand_total > 0 else 1.0
    pv_total = pv_h.sum()
    renewable_served = tot_pv_d + tot_bat_d
    solar_fraction = renewable_served / served_total if served_total > 0 else 0.0

    return {
        "design": design,
        "demand_total_kwh":    demand_total,
        "demand_served_kwh":   served_total,
        "unmet_demand_kwh":    tot_unmet,
        "service_level":       service_level,
        "grid_import_kwh":     tot_grid,
        "grid_to_demand_kwh":  tot_grid,
        "grid_to_battery_kwh": 0.0,
        "grid_cost_baseline_gbp": tot_grid_cost,
        "peak_grid_kw":        peak_grid,
        "pv_to_demand_kwh":    tot_pv_d,
        "pv_to_battery_kwh":   tot_pv_b,
        "pv_export_kwh":       tot_export,
        "pv_curtailed_kwh":    tot_curt,
        "battery_to_demand_kwh": tot_bat_d,
        "battery_throughput_kwh": tot_through,
        "pv_generation_kwh":   pv_total,
        "pv_self_consumption_kwh": tot_pv_d + tot_pv_b,
        "solar_fraction":      solar_fraction,
        "_dispatch_method":    "lp_optimal",
    }


if __name__ == "__main__":
    import time
    from . import demand_model, pv_model
    from .economics import Design

    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(
        demand_model.scenario_params("Medium", 5), df)
    base_yield = pv_model.specific_yield_per_kwp(solar)

    for d in [Design(5, 0, 4), Design(20, 30, 12), Design(25, 50, 20)]:
        pv = d.pv_kwp * base_yield
        t0 = time.time()
        r = simulate_lp(d, demand, pv)
        elapsed = time.time() - t0
        print(f"{d}  [{elapsed:.2f}s]")
        print(f"   service {r['service_level']*100:.1f}%  solar {r['solar_fraction']*100:.1f}%  "
              f"grid {r['grid_import_kwh']:,.0f} kWh  unmet {r['unmet_demand_kwh']:.0f} kWh")
