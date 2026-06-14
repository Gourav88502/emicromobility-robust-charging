"""
validation.py
=============
Independent sanity-check of the model against published benchmarks. A model that
is only internally consistent is not necessarily correct, so we confront seven
key outputs with literature/industry ranges and flag any that fall outside.

Sources are listed in REFERENCES.md (BEIS, IRENA, PVGIS, IEA PVPS, National Grid
ESO, Gossling 2020, Hollingsworth 2019).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from . import config, demand_model, pv_model, emissions, economics
from .energy_balance import simulate
from .economics import Design


def validate(df=None, solar=None, carbon=None, recommended: Design | None = None) -> pd.DataFrame:
    if df is None:
        df = demand_model.load_demand()
    if solar is None:
        solar = pv_model.load_solar()
    if carbon is None:
        carbon = emissions.load_carbon()
    if recommended is None:
        recommended = Design(25, 50, 8)

    # --- model outputs ----------------------------------------------------- #
    specific_yield = pv_model.specific_yield_per_kwp(solar).sum()
    mean_ci = carbon["carbon_intensity_gCO2_kWh"].mean()
    fleet = demand_model.mean_fleet_size(df)
    trip_dist = float(df["avg_trip_distance_km"].mean())

    # Evaluate design-performance metrics at the design's intended operating
    # point (the High scenario it is built to serve), not at low/medium demand
    # where an intentionally over-provisioned robust asset is under-utilised.
    demand = demand_model.hourly_demand_series(
        demand_model.scenario_params("High", config.OPTIMISATION_HORIZON_YEARS), df)
    pv = pv_model.pv_generation(recommended.pv_kwp, solar=solar)
    sim = simulate(recommended, demand, pv)
    costs = economics.annual_costs(recommended, sim)
    lcoe = economics.lcoe(recommended, sim)
    emis = emissions.emissions_analysis(sim, carbon)

    rows = [
        ("PV specific yield, Coventry/Warwick", specific_yield, 750, 1100, "kWh/kWp/yr",
         "PVGIS / IEA PVPS (UK optimal-tilt)"),
        ("Grid carbon intensity (West Midlands)", mean_ci, 110, 300, "gCO2/kWh",
         "National Grid ESO regional API, West Midlands"),
        ("Battery round-trip efficiency", config.BATTERY_ROUNDTRIP_EFF["baseline"] * 100,
         86, 95, "%", "IRENA 2017 / Mongird 2020 (Li-ion BESS)"),
        ("Shared e-bike mean trip distance", trip_dist, 1.5, 6.0, "km",
         "UoW Bikes scheme; Burani 2022 / Ouf 2023"),
        ("Solar fraction (recommended design)", sim["solar_fraction"] * 100, 15, 75, "%",
         "Commercial solar+storage self-consumption"),
        ("LCOE of charging served", lcoe, 0.10, 0.45, "£/kWh",
         "BEIS gen. cost + commercial tariff envelope"),
        ("Carbon saving vs grid-only", emis["carbon_saving_pct"], 10, 95, "%",
         "PV self-consumption displacement (marginal factor)"),
    ]
    out = pd.DataFrame(rows, columns=["metric", "model", "lit_low", "lit_high", "unit", "source"])
    out["model"] = out["model"].round(2)
    out["within_range"] = (out["model"] >= out["lit_low"]) & (out["model"] <= out["lit_high"])
    return out


if __name__ == "__main__":
    v = validate()
    print("MODEL VALIDATION vs published benchmarks\n")
    for _, r in v.iterrows():
        flag = "PASS" if r["within_range"] else "CHECK"
        print(f"  [{flag}] {r['metric']:38s} model={r['model']:>8g} {r['unit']:<9s} "
              f"lit {r['lit_low']}-{r['lit_high']}")
    print(f"\n{int(v['within_range'].sum())}/{len(v)} metrics within published range.")
