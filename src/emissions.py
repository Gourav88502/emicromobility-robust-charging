"""
emissions.py
============
Operational carbon analysis (Theme 3 sustainability narrative).

Compares the solar+storage station against a grid-only counterfactual using the
North East England regional carbon-intensity series (National Grid ESO). Reports
annual and lifetime CO2 savings and the implied carbon value.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from . import config


def load_carbon() -> pd.DataFrame:
    path = config.DATA_DIR / "carbon_intensity_ne_england.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. Run `python scripts/prepare_data.py` first.")
    return pd.read_csv(path, parse_dates=["datetime"])


def carbon_intensity_vector(carbon: pd.DataFrame | None = None) -> np.ndarray:
    if carbon is None:
        carbon = load_carbon()
    return carbon["carbon_intensity_gCO2_kWh"].to_numpy(dtype=float)


def emissions_analysis(result: dict,
                       carbon: pd.DataFrame | None = None) -> dict:
    """
    Carbon savings of the station vs a 100%-grid counterfactual, valued at the
    MARGINAL emissions factor (consequential accounting: on-site PV+storage
    displaces the marginal grid plant, ~gas CCGT, not the system average). The
    real regional average series is reported separately for context.
    """
    ci = carbon_intensity_vector(carbon)              # gCO2/kWh, len 8760
    mean_ci = float(ci.mean())
    marg = config.MARGINAL_CARBON_GCO2_KWH

    served = result["demand_served_kwh"]
    grid = result["grid_import_kwh"]
    # On-site renewable energy that displaced grid imports = served - grid import.
    displaced = max(served - grid, 0.0)

    emis_counterfactual_g = served * marg            # grid-only would import all of it
    emis_station_g = grid * marg                      # station still imports `grid`
    saving_g = displaced * marg
    saving_t = saving_g / 1e6                          # tonnes CO2
    lifetime_t = saving_t * config.PROJECT_LIFETIME_YEARS

    return {
        "mean_carbon_intensity_gCO2_kWh": mean_ci,
        "marginal_factor_gCO2_kWh": marg,
        "displaced_grid_kwh": displaced,
        "station_emissions_tCO2_yr": emis_station_g / 1e6,
        "counterfactual_emissions_tCO2_yr": emis_counterfactual_g / 1e6,
        "carbon_saving_tCO2_yr": saving_t,
        "carbon_saving_tCO2_lifetime": lifetime_t,
        "carbon_saving_pct": (saving_g / emis_counterfactual_g * 100)
                             if emis_counterfactual_g > 0 else 0.0,
        "carbon_value_gbp_yr": saving_t * config.CARBON_PRICE_PER_TONNE,
    }


def emissions_analysis_hourly(result: dict,
                              carbon: pd.DataFrame | None = None) -> dict:
    """
    HOUR-RESOLVED carbon accounting using the REAL National Grid ESO hourly
    carbon-intensity series (not a flat annual factor). Every kWh of on-site
    renewable energy that serves demand in hour h is credited at the actual grid
    carbon intensity CI[h] it displaces that hour. This is the rigorous,
    time-coupled version of emissions_analysis() and requires the hourly dispatch
    traces produced by energy_balance.simulate().

    Requires result to contain the hourly traces:
        _pv_to_demand, _batt_to_demand, _grid_import  (each length 8760).
    """
    ci = carbon_intensity_vector(carbon)                    # gCO2/kWh, len 8760
    pv_d = np.asarray(result.get("_pv_to_demand"))
    bat_d = np.asarray(result.get("_batt_to_demand"))
    grid = np.asarray(result.get("_grid_import"))
    if pv_d.ndim == 0 or pv_d.size <= 1:
        # No traces available — fall back to the flat-factor method.
        return emissions_analysis(result, carbon)

    n = min(len(ci), len(pv_d), len(bat_d), len(grid))
    ci = ci[:n]; pv_d = pv_d[:n]; bat_d = bat_d[:n]; grid = grid[:n]

    displaced_h = pv_d + bat_d                              # on-site energy served each hour
    served_h = pv_d + bat_d + grid                          # total demand met each hour

    saving_g = float((displaced_h * ci).sum())             # avoided emissions (real hourly CI)
    counterfactual_g = float((served_h * ci).sum())        # if all served from grid
    station_g = float((grid * ci).sum())
    saving_t = saving_g / 1e6
    return {
        "method": "hourly_real_grid_intensity",
        "mean_carbon_intensity_gCO2_kWh": float(ci.mean()),
        "displaced_grid_kwh": float(displaced_h.sum()),
        "station_emissions_tCO2_yr": station_g / 1e6,
        "counterfactual_emissions_tCO2_yr": counterfactual_g / 1e6,
        "carbon_saving_tCO2_yr": saving_t,
        "carbon_saving_tCO2_lifetime": saving_t * config.PROJECT_LIFETIME_YEARS,
        "carbon_saving_pct": (saving_g / counterfactual_g * 100) if counterfactual_g > 0 else 0.0,
        "carbon_value_gbp_yr": saving_t * config.CARBON_PRICE_PER_TONNE,
    }


def carbon_cost_frontier(pv_sizes=None, battery_kwh: float = 0.0,
                         n_chargers: int = 8, scenario: str = "High",
                         df=None, solar=None, carbon=None) -> pd.DataFrame:
    """
    Cost-vs-carbon trade-off along the PV axis (the multi-objective view a
    sustainability panel expects). For each PV size we run the full hourly
    dispatch, then report annual cost AND hour-resolved carbon saving — showing
    how much extra carbon each additional kWp buys, and at what cost.
    """
    from . import demand_model, pv_model, economics
    from .energy_balance import simulate

    if pv_sizes is None:
        pv_sizes = config.PV_SIZES_KWP
    if df is None:
        df = demand_model.load_dft()
    if solar is None:
        solar = pv_model.load_solar()
    if carbon is None:
        carbon = load_carbon()

    demand = demand_model.hourly_demand_series(
        demand_model.scenario_params(scenario, config.OPTIMISATION_HORIZON_YEARS), df)

    rows = []
    for pv_kwp in pv_sizes:
        d = economics.Design(pv_kwp, battery_kwh, n_chargers)
        pv = pv_model.pv_generation(pv_kwp, solar=solar)
        res = simulate(d, demand, pv)
        emis = emissions_analysis_hourly(res, carbon)
        costs = economics.annual_costs(d, res)
        rows.append({
            "pv_kwp": pv_kwp,
            "annual_cost_gbp": costs["total_annual_cost"],
            "carbon_saving_tCO2_yr": emis["carbon_saving_tCO2_yr"],
            "carbon_saving_pct": emis["carbon_saving_pct"],
            "solar_fraction_pct": res["solar_fraction"] * 100,
            "service_pct": res["service_level"] * 100,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from . import demand_model, pv_model
    from .energy_balance import simulate
    from .economics import Design
    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(demand_model.scenario_params("Medium"), df)
    design = Design(15, 30, 12)
    pv = pv_model.pv_generation(15, solar=solar)
    r = simulate(design, demand, pv)
    e = emissions_analysis(r)
    print(f"Mean grid CI       : {e['mean_carbon_intensity_gCO2_kWh']:.0f} gCO2/kWh")
    print(f"Carbon saving      : {e['carbon_saving_tCO2_yr']:.2f} tCO2/yr "
          f"({e['carbon_saving_pct']:.1f}%)")
    print(f"Lifetime saving    : {e['carbon_saving_tCO2_lifetime']:.1f} tCO2")
    print(f"Carbon value       : GBP {e['carbon_value_gbp_yr']:,.0f}/yr")
