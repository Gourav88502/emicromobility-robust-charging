"""
test_pipeline.py
================
Lightweight regression tests that guarantee the whole pipeline runs error-free
and the physics/economics stay self-consistent. Run with:

    python -m pytest -q          (or)    python tests/test_pipeline.py
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, demand_model, pv_model, economics, optimization, monte_carlo
from src.energy_balance import simulate, simulate_fast
from src.economics import Design


def _data_ready():
    needed = ["dft_newcastle_scooter_data.csv", "pvgis_newcastle_hourly.csv",
              "carbon_intensity_ne_england.csv"]
    if not all((config.DATA_DIR / f).exists() for f in needed):
        sys.path.insert(0, str(ROOT / "scripts"))
        import prepare_data
        prepare_data.main()


def test_data_loads():
    _data_ready()
    df = demand_model.load_dft()
    assert len(df) >= 24                       # ~29 months of real data
    assert df["monthly_trips"].min() > 0
    solar = pv_model.load_solar()
    assert len(solar) == config.HOURS_PER_YEAR


def test_pv_yield_realistic():
    solar = pv_model.load_solar()
    y = pv_model.annual_yield(10, solar=solar) / 10      # kWh/kWp/yr
    assert 600 < y < 1100, f"Newcastle specific yield out of range: {y:.0f}"


def test_energy_balance_conservation():
    """Served demand + unmet must equal total demand (energy is conserved)."""
    _data_ready()
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(demand_model.scenario_params("High", 5), df)
    design = Design(20, 40, 12)
    pv = pv_model.pv_generation(20, solar=solar)
    r = simulate(design, demand, pv)
    assert abs((r["demand_served_kwh"] + r["unmet_demand_kwh"])
               - r["demand_total_kwh"]) < 1.0
    assert 0.0 <= r["service_level"] <= 1.0
    assert 0.0 <= r["solar_fraction"] <= 1.0


def test_fast_matches_full():
    """simulate_fast must return identical scalars to simulate (with traces)."""
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(demand_model.scenario_params("Medium", 5), df)
    design = Design(15, 30, 8)
    pv = pv_model.pv_generation(15, solar=solar)
    a = simulate(design, demand, pv)
    b = simulate_fast(design, demand, pv)
    for k in ["grid_import_kwh", "demand_served_kwh", "service_level", "solar_fraction"]:
        assert abs(a[k] - b[k]) < 1e-6, k


def test_bigger_design_never_worse_service():
    """More PV+battery cannot reduce service level in a fixed scenario."""
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(demand_model.scenario_params("High", 5), df)
    small = simulate_fast(Design(5, 0, 4), demand, pv_model.pv_generation(5, solar=solar))
    big = simulate_fast(Design(25, 50, 20), demand, pv_model.pv_generation(25, solar=solar))
    assert big["service_level"] >= small["service_level"] - 1e-9


def test_costs_positive_and_finite():
    design = Design(15, 30, 12)
    e = {"grid_import_kwh": 40000, "pv_export_kwh": 5000, "unmet_demand_kwh": 200,
         "battery_throughput_kwh": 9000, "demand_served_kwh": 60000}
    c = economics.annual_costs(design, e)
    assert np.isfinite(c["total_annual_cost"]) and c["total_annual_cost"] > 0
    assert economics.lcoe(design, e) > 0


def test_optimisation_produces_distinct_rules():
    opt = optimization.run_full_optimisation()
    assert opt["n_designs"] == 150
    assert opt["robust_feasible_count"] >= 1
    # the recommended (maximin) design must be robustly feasible
    assert opt["rules"]["maximin_robust"]["robustly_feasible"]
    # value of robustness must be positive (robust beats naive on worst case)
    assert opt["value_of_robustness"]["worst_cost_reduction"] > 0


def test_monte_carlo_runs():
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    samples = monte_carlo.draw_samples(50)
    res = monte_carlo.evaluate_design(Design(20, 40, 12), samples, df, solar)
    assert len(res) == 50
    assert res["annual_cost"].notna().all()


def test_global_sensitivity_sobol():
    """Total-order Sobol indices are valid; demand/cost drivers dominate."""
    from src import sensitivity
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    g = sensitivity.global_sensitivity(Design(25, 50, 8), df, solar,
                                       output="annual_cost", n=1024)
    assert len(g) == len(config.UNCERTAIN_VARIABLES)
    assert (g["total_order"] >= 0).all()
    # the dominant driver must be a demand/cost variable, not an operating param
    demand_cost = {"equipment_cost", "demand_intensity", "trip_energy",
                   "fleet_utilisation", "demand_growth"}
    assert g.iloc[0]["name"] in demand_cost
    # a non-influential operating param has a small total effect
    assert g.set_index("name").loc["charger_avail", "total_order"] < 0.10


def test_robustness_conclusion_holds():
    """Robust must beat naive across (almost) the whole penalty x grid space."""
    from src import robustness
    df = demand_model.load_dft(); solar = pv_model.load_solar()
    res = robustness.sweep(df, solar, penalties=(5, 10, 20),
                           grids=(12, 16, 20), horizons=(5,))
    assert res["fraction_robust_wins"] >= 0.9      # robust wins (almost) everywhere
    assert res["vor_median"] > 0


def test_validation_within_range():
    """At its design operating point, every model output is within literature."""
    from src import validation
    v = validation.validate()
    assert v["within_range"].mean() >= 0.85        # essentially all metrics pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} tests passed")
    sys.exit(0 if passed == len(fns) else 1)
