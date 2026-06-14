"""
sensitivity.py
==============
One-at-a-time (OAT) tornado sensitivity analysis (EoI methodology step 5;
Saltelli et al., 2008). For a fixed design, each uncertain variable is swept
from its low to its high value while all others stay at baseline, and the swing
in a chosen output (annual cost, or unmet demand) is recorded and ranked.

This identifies which uncertainties most influence the economics of the chosen
station — telling the team where better data would most reduce risk.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from . import config, demand_model, pv_model, economics
from .energy_balance import simulate_fast
from .economics import Design


def _evaluate(design: Design, df, solar, *,
              demand_intensity, demand_growth, fleet_utilisation, trip_energy,
              pv_output, battery_eff, charger_avail, electricity_price,
              equipment_cost, year_index) -> dict:
    params = demand_model.DemandParams(
        trips_per_bike_day=demand_intensity,
        fleet_utilisation=fleet_utilisation, trip_energy_wh_per_km=trip_energy,
        demand_growth=demand_growth, year_index=year_index)
    demand = demand_model.hourly_demand_series(params, df)
    base_yield = pv_model.specific_yield_per_kwp(solar)
    pv = design.pv_kwp * base_yield * (pv_output / config.PV_PERFORMANCE_RATIO["baseline"])

    res = simulate_fast(design, demand, pv,
                        battery_rt_eff=battery_eff,
                        charger_availability=charger_avail)
    costs = economics.annual_costs(
        design, res, tariff=electricity_price, cost_multiplier=equipment_cost,
        battery_cost=config.BATTERY_CAPEX_PER_KWH["baseline"] * equipment_cost)
    return {"annual_cost": costs["total_annual_cost"],
            "service_level": res["service_level"],
            "unmet_kwh": res["unmet_demand_kwh"]}


def tornado(design: Design, df=None, solar=None,
            output: str = "annual_cost",
            year_index: int | None = None) -> pd.DataFrame:
    """
    Return a tidy tornado table for `design`, ranked by the absolute swing in
    `output` ('annual_cost', 'service_level' or 'unmet_kwh').
    """
    if df is None:
        df = demand_model.load_demand()
    if solar is None:
        solar = pv_model.load_solar()
    if year_index is None:
        year_index = config.OPTIMISATION_HORIZON_YEARS

    baseline_kwargs = dict(
        demand_intensity=config.TRIPS_PER_BIKE_DAY["medium"],
        demand_growth=config.DEMAND_GROWTH["medium"],
        fleet_utilisation=config.FLEET_UTILISATION["baseline"],
        trip_energy=config.TRIP_ENERGY_WH_PER_KM["baseline"],
        pv_output=config.PV_PERFORMANCE_RATIO["baseline"],
        battery_eff=config.BATTERY_ROUNDTRIP_EFF["baseline"],
        charger_avail=config.CHARGER_AVAILABILITY["baseline"],
        electricity_price=config.ELECTRICITY_TARIFF["baseline"],
        equipment_cost=1.0,
        year_index=year_index,
    )
    base_val = _evaluate(design, df, solar, **baseline_kwargs)[output]

    rows = []
    for v in config.UNCERTAIN_VARIABLES:
        lo_kwargs = dict(baseline_kwargs)
        hi_kwargs = dict(baseline_kwargs)
        lo_kwargs[v.name] = v.low
        hi_kwargs[v.name] = v.high
        lo_val = _evaluate(design, df, solar, **lo_kwargs)[output]
        hi_val = _evaluate(design, df, solar, **hi_kwargs)[output]
        rows.append({
            "variable": v.label,
            "name": v.name,
            "low_input": v.low,
            "high_input": v.high,
            "unit": v.unit,
            "low_output": lo_val,
            "high_output": hi_val,
            "baseline_output": base_val,
            "swing": abs(hi_val - lo_val),
        })
    out = pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)
    return out


def _evaluate_matrix(design, df, solar, base_yield, M, names, year_index, output):
    """Evaluate the model output for each row of input matrix M (dict name->array)."""
    n = len(M[names[0]])
    y = np.empty(n)
    for j in range(n):
        kw = {nm: float(M[nm][j]) for nm in names}
        res = _evaluate(design, df, solar, year_index=year_index, **kw)
        y[j] = res[output]
    return y


def global_sensitivity(design: Design, df=None, solar=None,
                       output: str = "annual_cost", n: int = 2048,
                       seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    """
    Variance-based global sensitivity via the Saltelli pick-freeze estimator
    (Saltelli et al., 2010), returning first-order (S_i) and total-order (S_Ti)
    Sobol indices for every uncertain input. S_i is the main effect; S_Ti also
    captures interactions, so S_Ti - S_i quantifies interaction strength.
    Uses n*(D+2) independent model evaluations.
    """
    if df is None:
        df = demand_model.load_demand()
    if solar is None:
        solar = pv_model.load_solar()
    base_yield = pv_model.specific_yield_per_kwp(solar)
    year_index = config.OPTIMISATION_HORIZON_YEARS
    rng = np.random.default_rng(seed)
    vars_ = config.UNCERTAIN_VARIABLES
    names = [v.name for v in vars_]

    def sample_matrix():
        out = {}
        for v in vars_:
            mode = min(max(v.baseline, v.low), v.high)
            out[v.name] = (rng.triangular(v.low, mode, v.high, n) if v.high > v.low
                           else np.full(n, mode))
        return out

    A, B = sample_matrix(), sample_matrix()
    yA = _evaluate_matrix(design, df, solar, base_yield, A, names, year_index, output)
    yB = _evaluate_matrix(design, df, solar, base_yield, B, names, year_index, output)
    varY = np.var(np.concatenate([yA, yB]), ddof=1)
    if varY <= 0:
        varY = 1.0

    rows = []
    for v in vars_:
        ABi = dict(A); ABi[v.name] = B[v.name]
        yABi = _evaluate_matrix(design, df, solar, base_yield, ABi, names, year_index, output)

        # Point estimates (Saltelli 2010 / Jansen 1999)
        Si  = float(np.mean(yB * (yABi - yA)) / varY)
        STi = float(np.mean((yA - yABi) ** 2) / (2 * varY))

        # Bootstrap 95 % CI on each Sobol index (Archer et al. 1997;
        # Saltelli et al. 2010 recommend 500–2000 resamples for n >= 512).
        n_boot = 1000
        rng_b = np.random.default_rng(seed + 1)
        Si_boot, STi_boot = [], []
        for _ in range(n_boot):
            idx = rng_b.integers(0, n, size=n)
            _yA = yA[idx]; _yB = yB[idx]; _yABi = yABi[idx]
            _var = max(np.var(np.concatenate([_yA, _yB]), ddof=1), 1e-12)
            Si_boot.append(np.mean(_yB * (_yABi - _yA)) / _var)
            STi_boot.append(np.mean((_yA - _yABi) ** 2) / (2 * _var))

        si_lo,  si_hi  = float(np.percentile(Si_boot, 2.5)),  float(np.percentile(Si_boot, 97.5))
        sti_lo, sti_hi = float(np.percentile(STi_boot, 2.5)), float(np.percentile(STi_boot, 97.5))

        rows.append({
            "variable": v.label, "name": v.name,
            "first_order":  max(Si, 0.0),
            "total_order":  max(STi, 0.0),
            "si_ci_lo":     max(si_lo, 0.0),
            "si_ci_hi":     max(si_hi, 0.0),
            "sti_ci_lo":    max(sti_lo, 0.0),
            "sti_ci_hi":    max(sti_hi, 0.0),
        })

    out = pd.DataFrame(rows).sort_values("total_order", ascending=False).reset_index(drop=True)
    out["pct_variance"] = (out["first_order"] * 100).round(1)
    out["pct_total"]    = (out["total_order"] * 100).round(1)
    return out


if __name__ == "__main__":
    df = demand_model.load_demand()
    solar = pv_model.load_solar()
    design = Design(25, 50, 4)            # robust recommendation
    t = tornado(design, df, solar, output="annual_cost")
    print(f"Tornado sensitivity (annual cost) for {design}\n")
    print(f"{'Variable':28s}{'Low GBP':>12s}{'High GBP':>12s}{'Swing GBP':>12s}")
    for _, r in t.iterrows():
        print(f"{r['variable']:28s}{r['low_output']:>12,.0f}{r['high_output']:>12,.0f}{r['swing']:>12,.0f}")

    print("\nGlobal sensitivity — Sobol indices (annual cost), Saltelli estimator:")
    print(f"  {'Variable':36s}{'first-order':>12s}{'total-order':>12s}")
    g = global_sensitivity(design, df, solar, output="annual_cost", n=2048)
    for _, r in g.iterrows():
        print(f"  {r['variable']:36s}{r['pct_variance']:11.1f}%{r['pct_total']:11.1f}%")
    print(f"  {'(sum)':36s}{g['pct_variance'].sum():11.1f}%{g['pct_total'].sum():11.1f}%")
