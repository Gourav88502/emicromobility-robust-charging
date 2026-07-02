"""
build_demo_site.py
==================
Exports the exact model inputs + reference outputs needed by the interactive
demo website (docs/index.html), and injects them into the page so it is a
SINGLE self-contained file that opens offline on any laptop (the in-person
round requirement: "ensure your github files can be opened from the
presentation laptop").

The browser demo re-implements the greedy dispatch (energy_balance._dispatch)
and the annualised-cost model (economics.annual_costs) in JavaScript. This
script therefore exports:

  1. pv_per_kwp        - the real PVGIS Coventry specific yield (8,760 h)
  2. unit_profile      - month weight x weekday/weekend x smart-charging
                         weights, so demand_t = annual_kwh/365 * unit_profile[t]
  3. every economic / technical constant the JS engine needs (from config.py)
  4. the 15-scenario robust set (annual kWh + probabilities, horizon year 5)
  5. reference results computed by the REAL Python engine for a spread of
     designs, so the page can self-validate the JS engine at load time
  6. headline result tables (results.json, Pareto frontier, storage boundary,
     Theme-2 profiles, validation table) for the static charts.

Run:  python scripts/build_demo_site.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, demand_model, pv_model, economics, optimization  # noqa: E402
from src.economics import Design                                         # noqa: E402
from src.energy_balance import simulate_fast                             # noqa: E402

DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

START_MARK = "/*__DEMO_DATA_START__*/"
END_MARK = "/*__DEMO_DATA_END__*/"


def _round_list(arr, nd):
    return [round(float(x), nd) for x in np.asarray(arr).ravel()]


def build_payload() -> dict:
    df = demand_model.load_demand()
    solar = pv_model.load_solar()
    pv_per_kwp = pv_model.specific_yield_per_kwp(solar)          # 8760, kWh/kWp

    # ---- demand unit profile: demand_t = annual_kwh / 365 * unit_profile[t]
    month_w = demand_model.seasonal_monthly_weights(df)
    unit_profile = (month_w[demand_model._MONTH_IDX]
                    * demand_model._DOW_SCALE
                    * demand_model._smart_charging_weights())

    # sanity: rebuilding demand from the unit profile must match the model
    p = demand_model.scenario_params("High", config.OPTIMISATION_HORIZON_YEARS)
    ref = demand_model.hourly_demand_series(p, df)
    annual = demand_model.annual_demand_kwh(p, df)
    rebuilt = annual / 365.0 * unit_profile
    assert np.allclose(ref, rebuilt, rtol=1e-9), "unit-profile reconstruction failed"

    # ---- 15-scenario robust set at the design horizon
    # NOTE: export the annual-demand PARAMETER (annual_demand_kwh), not the
    # hourly-array sum: Python builds demand_t = annual/365 * unit_profile[t],
    # and unit_profile does not sum to exactly 365 (month lengths, weekend
    # count). The JS engine reconstructs with the same formula, so it must use
    # the same annual parameter or every scenario drifts by ~0.4-0.9%.
    scenarios = optimization.build_scenarios(df)
    scen_export = []
    for s in scenarios:
        params = demand_model.DemandParams(
            trips_per_bike_day=s.trips_per_bike_day,
            fleet_utilisation=s.fleet_utilisation,
            trip_energy_wh_per_km=config.TRIP_ENERGY_WH_PER_KM["baseline"],
            demand_growth=s.demand_growth,
            year_index=config.OPTIMISATION_HORIZON_YEARS)
        annual = demand_model.annual_demand_kwh(params, df)
        rebuilt = annual / 365.0 * unit_profile
        assert np.allclose(s.demand_kwh, rebuilt, rtol=1e-9), \
            f"scenario reconstruction failed: {s.name}"
        scen_export.append({
            "name": s.name, "level": s.demand_level,
            "tpd": s.trips_per_bike_day, "util": s.fleet_utilisation,
            "growth": round(s.demand_growth, 4),
            "prob": round(s.probability, 6),
            "annual_kwh": round(float(annual), 4),
        })

    # ---- reference results from the REAL Python engine (JS self-validation)
    refs = []
    ref_designs = [Design(5, 0, 4), Design(15, 0, 8), Design(10, 20, 8),
                   Design(25, 50, 20), Design(5, 10, 12), Design(15, 0, 8)]
    # de-dup while keeping order
    seen = set()
    ref_designs = [d for d in ref_designs
                   if d.key not in seen and not seen.add(d.key)]
    grid_caps = [15.0, 15.0, 15.0, 15.0, 8.0]
    for d, gcap in zip(ref_designs, grid_caps):
        pv = d.pv_kwp * pv_per_kwp
        costs, services = [], []
        for s in scenarios:
            r = simulate_fast(d, s.demand_kwh, pv, grid_kw=gcap)
            c = economics.annual_costs(d, r)
            costs.append(c["total_annual_cost"])
            services.append(r["service_level"])
        probs = np.array([s.probability for s in scenarios])
        refs.append({
            "pv": d.pv_kwp, "batt": d.battery_kwh, "bays": d.n_chargers,
            "grid": gcap,
            "worst_cost": round(float(np.max(costs)), 2),
            "expected_cost": round(float(np.dot(costs, probs)), 2),
            "min_service": round(float(np.min(services)), 6),
        })

    # ---- static result tables
    results = json.loads((ROOT / "outputs" / "results.json").read_text())
    pareto = pd.read_csv(ROOT / "outputs" / "pareto_frontier.csv").to_dict("records")
    threshold = pd.read_csv(ROOT / "outputs" / "grid_battery_threshold.csv").to_dict("records")
    validation = pd.read_csv(ROOT / "outputs" / "validation_benchmarks.csv").to_dict("records")
    sustain = json.loads((ROOT / "outputs" / "battery_sustainability.json").read_text())

    payload = {
        "site": {"name": config.SITE_NAME, "lat": config.SITE_LAT,
                 "lon": config.SITE_LON},
        "pv_per_kwp": _round_list(pv_per_kwp, 5),
        "unit_profile": _round_list(unit_profile, 8),
        "demand_const": {
            "fleet_mean": round(float(demand_model.mean_fleet_size(df)), 2),
            "trip_dist_km": round(float(df["avg_trip_distance_km"].mean()), 4),
            "station_share": config.STATION_DEMAND_SHARE,
            "growth_saturation": config.DEMAND_GROWTH_SATURATION,
            "horizon_years": config.OPTIMISATION_HORIZON_YEARS,
            "trip_energy_whkm": config.TRIP_ENERGY_WH_PER_KM,
            "tpd": config.TRIPS_PER_BIKE_DAY,
            "util": config.FLEET_UTILISATION,
            "growth": config.DEMAND_GROWTH,
        },
        "engine": {
            "tou": config.TOU_TARIFF,
            "battery_rt_eff": config.BATTERY_ROUNDTRIP_EFF["baseline"],
            "battery_dod": config.BATTERY_DOD,
            "charger_kw": config.CHARGER_POWER_KW["baseline"],
            "charger_avail": config.CHARGER_AVAILABILITY["baseline"],
            "grid_kw": config.GRID_CONNECTION_KW,
            "service_target": config.SERVICE_LEVEL_TARGET,
            "unmet_penalty": config.UNMET_DEMAND_PENALTY,
        },
        "econ": {
            "pv_capex": config.PV_CAPEX_PER_KWP["baseline"],
            "batt_capex": config.BATTERY_CAPEX_PER_KWH["baseline"],
            "charger_capex": config.CHARGER_CAPEX_PER_UNIT["baseline"],
            "install_frac": config.INSTALL_FRACTION["baseline"],
            "opex_frac": config.OPEX_FRACTION["baseline"],
            "tariff": config.ELECTRICITY_TARIFF["baseline"],
            "feed_in": config.FEED_IN_TARIFF,
            "demand_charge": config.DEMAND_CHARGE_PER_KW_YEAR,
            "discount_rate": config.DISCOUNT_RATE,
            "lifetime_years": config.PROJECT_LIFETIME_YEARS,
            "pv_lifetime_years": config.PV_LIFETIME_YEARS,
            "battery_cycle_life": config.BATTERY_CYCLE_LIFE["baseline"],
            "battery_calendar_years": config.BATTERY_CALENDAR_LIFE_YEARS,
            "carbon_price": config.CARBON_PRICE_PER_TONNE,
        },
        "carbon": {
            "marginal_g_kwh": config.MARGINAL_CARBON_GCO2_KWH,
            "avg_g_kwh": results["emissions"]["mean_carbon_intensity_gCO2_kWh"],
        },
        "design_space": {
            "pv": config.PV_SIZES_KWP,
            "batt": config.BATTERY_SIZES_KWH,
            "bays": config.CHARGER_COUNTS,
        },
        "scenarios": scen_export,
        "reference_results": refs,
        "results": results,
        "pareto": pareto,
        "threshold": threshold,
        "validation": validation,
        "battery_sustainability": sustain,
    }
    return payload


def inject(payload: dict) -> None:
    html_path = DOCS / "index.html"
    html = html_path.read_text(encoding="utf-8")
    a = html.index(START_MARK)
    b = html.index(END_MARK)
    blob = json.dumps(payload, separators=(",", ":"))
    html = (html[: a + len(START_MARK)]
            + f"\nwindow.DEMO_DATA = {blob};\n"
            + html[b:])
    html_path.write_text(html, encoding="utf-8")
    # root-level copy so the organiser can simply double-click the repo download
    (ROOT / "demo.html").write_text(html, encoding="utf-8")
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"docs/index.html rebuilt with embedded data ({size_kb:,.0f} KB); "
          f"copied to demo.html")


if __name__ == "__main__":
    payload = build_payload()
    if not (DOCS / "index.html").exists():
        raise SystemExit("docs/index.html template missing - create it first")
    inject(payload)
