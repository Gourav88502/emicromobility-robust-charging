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
        trips_per_scooter_day=demand_intensity,
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
        df = demand_model.load_dft()
    if solar is None:
        solar = pv_model.load_solar()
    if year_index is None:
        year_index = config.OPTIMISATION_HORIZON_YEARS

    baseline_kwargs = dict(
        demand_intensity=config.TRIPS_PER_SCOOTER_DAY["medium"],
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


if __name__ == "__main__":
    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    design = Design(25, 50, 4)            # robust recommendation
    t = tornado(design, df, solar, output="annual_cost")
    print(f"Tornado sensitivity (annual cost) for {design}\n")
    print(f"{'Variable':28s}{'Low GBP':>12s}{'High GBP':>12s}{'Swing GBP':>12s}")
    for _, r in t.iterrows():
        print(f"{r['variable']:28s}{r['low_output']:>12,.0f}{r['high_output']:>12,.0f}{r['swing']:>12,.0f}")
