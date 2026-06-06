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
        +  weekday / weekend distinction (DfT data, 1.25x weekend)  ->  daily kWh
        +  24-hour demand shape (peak 17-21h, smart-charging aware)  ->  hourly kWh

Weekday/Weekend Modelling
--------------------------
Shared e-micromobility exhibits a strong day-of-week effect: weekend trip
intensity is typically 1.2–1.4× weekdays in the DfT Newcastle data (riders
use scooters for leisure rather than commuting).  Ignoring this collapses
two structurally different demand regimes into one, underestimating the
realistic 48-hour peak and the battery sizing requirement at hubs with
no weekend grid top-up.

The day-of-week scaling is applied BEFORE the hourly shape so that the
smart controller sees the correct daily total.  Correlated weather–demand
tail events (hot summer Saturdays) are captured by the shared Monte-Carlo
demand-regime parameter.
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


_WEIGHTS_CACHE: dict[int, np.ndarray] = {}


def seasonal_monthly_weights(df: pd.DataFrame) -> np.ndarray:
    """12-element vector of normalised monthly demand multipliers (mean = 1)."""
    # Content-based cache key (robust to id() reuse after garbage collection).
    key = hash((int(df["monthly_trips"].sum()), len(df)))
    cached = _WEIGHTS_CACHE.get(key)
    if cached is not None:
        return cached
    monthly = df.groupby("month_num")["monthly_trips"].mean()
    monthly = monthly.reindex(range(1, 13)).interpolate().bfill().ffill()
    w = (monthly / monthly.mean()).values
    _WEIGHTS_CACHE[key] = w
    return w


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
    # Logistic-style saturation cap: adoption is an S-curve, not pure exponential.
    growth = min((1 + params.demand_growth) ** params.year_index,
                 config.DEMAND_GROWTH_SATURATION)
    return daily_kwh * 365.0 * growth


# Static hour-of-year calendar — computed once and reused (big speed-up for the
# tens of thousands of demand-series builds in Monte-Carlo / sensitivity).
_HOURS = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
_MONTH_IDX = _HOURS.month.values - 1
_HOUR_IDX  = _HOURS.hour.values
_DOW_IDX   = _HOURS.dayofweek.values          # 0=Mon, …, 6=Sun
_IS_WEEKEND = (_DOW_IDX >= 5).astype(float)   # Sat=5, Sun=6 -> 1.0; Mon-Fri -> 0.0

_DEFAULT_SHAPE = normalised_hourly_shape()
_SMART_WEIGHT_CACHE: np.ndarray | None = None

# Weekday / weekend demand scaling factors (empirical from DfT Newcastle data).
# Weekend trip intensity is ~25 % higher than weekday (leisure vs commute mix).
# Weighted average preserves the correct weekly total (2/7 × 1.25 + 5/7 × 1.0 = 1.071),
# so the annual totals from annual_demand_kwh() are not distorted.
_WEEKEND_MULTIPLIER = 1.25   # Sat/Sun vs Mon-Fri
_WEEKDAY_MULT = 1.0 / (5/7 + 2/7 * _WEEKEND_MULTIPLIER)   # renormalise to preserve total
_WEEKEND_MULT = _WEEKEND_MULTIPLIER * _WEEKDAY_MULT

# Per-hour day-of-week scaling vector (length 8760)
_DOW_SCALE = np.where(_IS_WEEKEND, _WEEKEND_MULT, _WEEKDAY_MULT)


def _smart_charging_weights() -> np.ndarray:
    """
    8,760-hour SMART-charging allocation weights, normalised so each DAY sums to 1.

    The smart controller schedules each day's flexible charging energy across the
    depot dwell window, favouring hours that (a) have vehicles present, (b) have
    on-site PV available, and (c) sit in cheap off-peak tariff periods. This
    flattens the load and shifts it overnight / into sun — the realistic outcome
    of managed depot charging (Theme 2).
    """
    global _SMART_WEIGHT_CACHE
    if _SMART_WEIGHT_CACHE is not None:
        return _SMART_WEIGHT_CACHE

    avail = np.asarray(config.VEHICLE_AVAILABILITY, float)[_HOUR_IDX]

    # Off-peak desirability from the ToU tariff (cheapest hour -> 1, dearest -> 0).
    tou = np.asarray(config.TOU_TARIFF, float)
    offpeak24 = (tou.max() - tou) / (tou.max() - tou.min() + 1e-9)
    offpeak = offpeak24[_HOUR_IDX]

    # PV-availability shape (0-1), from the real solar series if present.
    try:
        from . import pv_model
        pv = pv_model.specific_yield_per_kwp()
        pv_norm = pv / (pv.max() + 1e-9)
    except Exception:
        pv_norm = np.zeros(config.HOURS_PER_YEAR)

    weight = avail * (1.0 + config.SMART_PV_WEIGHT * pv_norm
                      + config.SMART_OFFPEAK_WEIGHT * offpeak)
    # normalise within each day so a day's weights sum to 1
    daily_sum = weight.reshape(-1, 24).sum(axis=1)
    weight = weight / np.repeat(daily_sum, 24)
    _SMART_WEIGHT_CACHE = weight
    return weight


def hourly_demand_series(params: DemandParams,
                         df: pd.DataFrame | None = None) -> np.ndarray:
    """8,760-hour charging-energy demand profile (kWh per hour)."""
    if df is None:
        df = load_dft()
    annual_kwh = annual_demand_kwh(params, df)
    month_w = seasonal_monthly_weights(df)
    base_daily = annual_kwh / 365.0
    daily_by_month = base_daily * month_w[_MONTH_IDX]

    # Apply weekday/weekend scaling to the daily totals.
    # _DOW_SCALE is 1 for weekdays, ~1.25× (normalised) for weekends.
    daily_scaled = daily_by_month * _DOW_SCALE

    if config.SMART_CHARGING and params.hourly_shape is None:
        # `daily_scaled` is the day's total energy (constant within a day); the
        # smart weights sum to 1 per day, so this distributes each day's flexible
        # energy across the dwell window following PV + off-peak tariff.
        return (daily_scaled * _smart_charging_weights()).astype(float)

    hour_shape = _DEFAULT_SHAPE if params.hourly_shape is None \
        else normalised_hourly_shape(params.hourly_shape)
    return (daily_scaled * hour_shape[_HOUR_IDX]).astype(float)


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
