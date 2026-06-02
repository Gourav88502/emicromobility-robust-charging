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
    Carbon savings of the station vs a 100%-grid counterfactual.

    Uses hourly carbon intensity where hourly traces are available (preferred),
    otherwise an annual-mean intensity on aggregate energy.
    """
    ci = carbon_intensity_vector(carbon)              # gCO2/kWh, len 8760
    mean_ci = float(ci.mean())

    served = result["demand_served_kwh"]
    grid = result["grid_import_kwh"]

    if "_grid_import" in result:
        grid_hourly = np.asarray(result["_grid_import"])
        served_hourly = (np.asarray(result["_pv_to_demand"])
                         + np.asarray(result["_batt_to_demand"])
                         + grid_hourly)
        emis_station_g = float(np.sum(grid_hourly * ci))
        emis_counterfactual_g = float(np.sum(served_hourly * ci))
    else:
        emis_station_g = grid * mean_ci
        emis_counterfactual_g = served * mean_ci

    saving_g = emis_counterfactual_g - emis_station_g
    saving_t = saving_g / 1e6                          # tonnes CO2
    lifetime_t = saving_t * config.PROJECT_LIFETIME_YEARS

    return {
        "mean_carbon_intensity_gCO2_kWh": mean_ci,
        "station_emissions_tCO2_yr": emis_station_g / 1e6,
        "counterfactual_emissions_tCO2_yr": emis_counterfactual_g / 1e6,
        "carbon_saving_tCO2_yr": saving_t,
        "carbon_saving_tCO2_lifetime": lifetime_t,
        "carbon_saving_pct": (saving_g / emis_counterfactual_g * 100)
                             if emis_counterfactual_g > 0 else 0.0,
        "carbon_value_gbp_yr": saving_t * config.CARBON_PRICE_PER_TONNE,
    }


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
