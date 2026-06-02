"""
demand_model.py
===============
Turns the real DfT Newcastle/Neuron monthly data into an 8,760-hour charging
energy-demand series, for Low / Medium / High scenarios and for arbitrary
Monte-Carlo parameter draws.

Pipeline
--------
monthly trips & fleet (DfT)  ->  seasonal monthly weights
        +  scenario trips/scooter/day, fleet utilisation, growth
        +  trip distance (km) x trip energy (Wh/km)            ->  daily kWh
        +  24-hour demand shape (peak 17-21h)                  ->  hourly kWh
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config


@dataclass
class DemandParams:
    """Parameters that define one realised demand series."""
    trips_per_scooter_day: float
    fleet_utilisation: float
    trip_energy_wh_per_km: float
    demand_growth: float = 0.0
    year_index: int = 0                     # 0 = first project year
    hourly_shape: np.ndarray | None = None


def load_dft() -> pd.DataFrame:
    path = config.DATA_DIR / "dft_newcastle_scooter_data.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. Run `python scripts/prepare_data.py` first.")
    return pd.read_csv(path, parse_dates=["date"])


def seasonal_monthly_weights(df: pd.DataFrame) -> np.ndarray:
    """12-element vector of normalised monthly demand multipliers (mean = 1)."""
    monthly = df.groupby("month_num")["monthly_trips"].mean()
    monthly = monthly.reindex(range(1, 13)).interpolate().bfill().ffill()
    return (monthly / monthly.mean()).values


def normalised_hourly_shape(shape: np.ndarray | None = None) -> np.ndarray:
    s = np.asarray(config.HOURLY_DEMAND_SHAPE if shape is None else shape, float)
    return s / s.sum()


def mean_fleet_size(df: pd.DataFrame) -> float:
    return float(df["fleet_size"].mean())


def annual_demand_kwh(params: DemandParams, df: pd.DataFrame | None = None) -> float:
    """Total annual charging-energy demand (kWh) for the given parameters."""
    if df is None:
        df = load_dft()
    fleet = mean_fleet_size(df)
    trip_dist_km = float(df["avg_trip_distance_km"].mean())

    # Station daily energy = fleet x trips/scooter/day x (fraction of fleet
    # needing a charge that day) x (share of those charges captured by this hub)
    # x energy per trip. Two-stage demand decomposition (see config docstrings).
    daily_trips = (fleet * params.trips_per_scooter_day
                   * params.fleet_utilisation * config.STATION_DEMAND_SHARE)
    energy_per_trip_kwh = trip_dist_km * params.trip_energy_wh_per_km / 1000.0
    daily_kwh = daily_trips * energy_per_trip_kwh
    growth = (1 + params.demand_growth) ** params.year_index
    return daily_kwh * 365.0 * growth


def hourly_demand_series(params: DemandParams,
                         df: pd.DataFrame | None = None) -> np.ndarray:
    """8,760-hour charging-energy demand profile (kWh per hour)."""
    if df is None:
        df = load_dft()
    annual_kwh = annual_demand_kwh(params, df)

    hours = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
    month_w = seasonal_monthly_weights(df)
    hour_shape = normalised_hourly_shape(params.hourly_shape)

    month_idx = hours.month.values - 1
    hour_idx = hours.hour.values

    # Distribute annual energy: by month (seasonal weight) then within day (shape).
    base_daily = annual_kwh / 365.0
    daily_by_month = base_daily * month_w[month_idx]
    hourly = daily_by_month * hour_shape[hour_idx]
    return hourly.astype(float)


def monthly_demand_series(params: DemandParams, df: pd.DataFrame | None = None) -> np.ndarray:
    """12-element monthly charging-demand vector (kWh) for the demand fan."""
    if df is None:
        df = load_dft()
    annual = annual_demand_kwh(params, df)
    w = seasonal_monthly_weights(df)             # mean ~1 across 12 months
    return annual * w / w.sum()


def scenario_params(scenario: str, year_index: int = 0) -> DemandParams:
    """Build DemandParams for the headline Low / Medium / High scenarios."""
    table = config.scenario_table()
    if scenario not in table:
        raise ValueError(f"scenario must be one of {list(table)}")
    s = table[scenario]
    return DemandParams(
        trips_per_scooter_day=s["trips_per_scooter_day"],
        fleet_utilisation=s["fleet_utilisation"],
        trip_energy_wh_per_km=config.TRIP_ENERGY_WH_PER_KM["baseline"],
        demand_growth=s["demand_growth"],
        year_index=year_index,
    )


def scenario_summary() -> pd.DataFrame:
    """Annual demand for each headline scenario (year 0 and final year)."""
    df = load_dft()
    rows = []
    for sc in ("Low", "Medium", "High"):
        p0 = scenario_params(sc, 0)
        pN = scenario_params(sc, config.PROJECT_LIFETIME_YEARS - 1)
        rows.append({
            "scenario": sc,
            "trips_per_scooter_day": p0.trips_per_scooter_day,
            "fleet_utilisation": p0.fleet_utilisation,
            "demand_growth": p0.demand_growth,
            "annual_kwh_year0": round(annual_demand_kwh(p0, df), 0),
            "annual_kwh_final": round(annual_demand_kwh(pN, df), 0),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = load_dft()
    print(f"Mean fleet size      : {mean_fleet_size(df):.0f} e-scooters")
    print(f"Mean trip distance   : {df['avg_trip_distance_km'].mean():.2f} km")
    print(f"Seasonal weights     : {np.round(seasonal_monthly_weights(df), 2)}")
    print("\nScenario annual demand (kWh):")
    print(scenario_summary().to_string(index=False))
    p = scenario_params("Medium")
    h = hourly_demand_series(p, df)
    print(f"\nMedium hourly series : sum={h.sum():,.0f} kWh, peak={h.max():.2f} kWh/h")
