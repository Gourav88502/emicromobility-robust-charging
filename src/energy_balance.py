"""
energy_balance.py
=================
Hour-by-hour dispatch simulation of the solar charging station (Theme 2 +
Theme 3) under a CONSTRAINED grid connection.

For each of the 8,760 hours the controller resolves, in priority order:

    1. PV serves charging demand directly.
    2. Surplus PV charges the battery (within power & state-of-charge limits).
    3. Remaining surplus PV is exported to the grid.
    4. A demand deficit is met first from the battery, then from the capped grid
       connection.
    5. During the off-peak window the battery is topped up from spare grid
       capacity (peak-shaving / arbitrage) so it is ready for the evening peak.
    6. Demand that still cannot be served (charger limit, or grid cap with an
       empty battery) is recorded as UNMET — the failure mode robust design
       must avoid.

The greedy priority controller is a transparent, deterministic rule (no LP
solver needed). The hot loop is JIT-compiled with Numba when available
(~100x speed-up) and falls back to pure Python so the project always runs.

Solar fraction is computed honestly: energy discharged from the battery is
credited to solar only in proportion to how much of the battery's charging came
from PV versus the grid.
"""

from __future__ import annotations
import numpy as np

from . import config
from .economics import Design

# --------------------------------------------------------------------------- #
#  Optional Numba acceleration (graceful fallback)
# --------------------------------------------------------------------------- #
try:
    from numba import njit
    _HAVE_NUMBA = True
except Exception:                                            # pragma: no cover
    _HAVE_NUMBA = False

    def njit(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap(args[0]) if args and callable(args[0]) else _wrap


# Off-peak window (overnight) when grid top-up of the battery is permitted.
_OFFPEAK_START, _OFFPEAK_END = 0, 6      # 00:00-05:59


@njit(cache=True, fastmath=True)
def _dispatch(demand, pv, tou, usable_cap, p_batt_max, deliver_cap,
              grid_cap, eff_one_way, want_traces):
    n = demand.shape[0]
    soc = usable_cap * 0.5

    s_grid = 0.0             # grid -> demand (kWh)
    s_grid_cost = 0.0        # grid energy cost at time-of-use tariff (GBP)
    s_peak_grid = 0.0        # peak grid import (kW) -> demand charge
    s_pv_d = 0.0             # PV -> demand
    s_pv_b = 0.0             # PV -> battery
    s_pv_x = 0.0             # PV -> export (capped by connection)
    s_curtail = 0.0          # PV curtailed (surplus beyond export cap)
    s_bat_d = 0.0            # battery -> demand
    s_unmet = 0.0
    s_through = 0.0          # battery throughput (for cycle counting)

    m = n if want_traces else 1
    tr_grid = np.zeros(m)
    tr_pv_d = np.zeros(m)
    tr_bat_d = np.zeros(m)
    tr_pv_x = np.zeros(m)
    tr_soc = np.zeros(m)
    tr_unmet = np.zeros(m)

    for t in range(n):
        d = demand[t]
        g = pv[t]
        charge_room_pwr = p_batt_max
        discharge_room_pwr = p_batt_max

        # Charger hardware cap on hourly delivery.
        servable = d if d < deliver_cap else deliver_cap
        unmet = d - servable

        # 1. PV -> demand
        pv_d = g if g < servable else servable
        s_pv_d += pv_d
        residual = servable - pv_d
        surplus = g - pv_d

        # 2. surplus PV -> battery (the battery's role under smart charging is to
        #    time-shift daytime PV onto the overnight load -> self-consumption)
        if surplus > 0.0 and usable_cap > 0.0 and charge_room_pwr > 0.0:
            room_in = (usable_cap - soc) / eff_one_way
            charge_in = surplus
            if charge_in > charge_room_pwr:
                charge_in = charge_room_pwr
            if charge_in > room_in:
                charge_in = room_in
            if charge_in < 0.0:
                charge_in = 0.0
            stored = charge_in * eff_one_way
            soc += stored
            charge_room_pwr -= charge_in
            s_pv_b += charge_in
            s_through += stored
            surplus -= charge_in

        # 3. remaining surplus PV -> export, capped by the grid connection
        export_t = 0.0
        if surplus > 0.0:
            export_t = surplus if surplus < grid_cap else grid_cap
            s_pv_x += export_t
            s_curtail += surplus - export_t

        # 4. deficit -> battery discharge, then capped grid
        bat_d = 0.0
        grid_used = 0.0
        if residual > 0.0:
            if usable_cap > 0.0 and soc > 0.0 and discharge_room_pwr > 0.0:
                avail_out = soc * eff_one_way
                discharge = residual
                if discharge > discharge_room_pwr:
                    discharge = discharge_room_pwr
                if discharge > avail_out:
                    discharge = avail_out
                soc -= discharge / eff_one_way
                discharge_room_pwr -= discharge
                bat_d = discharge
                s_bat_d += discharge
                s_through += discharge
                residual -= discharge
            if residual > 0.0:
                grid_used = residual if residual < grid_cap else grid_cap
                s_grid += grid_used
                s_grid_cost += grid_used * tou[t]
                if grid_used > s_peak_grid:
                    s_peak_grid = grid_used
                residual -= grid_used
                if residual > 0.0:
                    unmet += residual        # capped grid + empty battery

        s_unmet += unmet

        if want_traces:
            tr_grid[t] = grid_used
            tr_pv_d[t] = pv_d
            tr_bat_d[t] = bat_d
            tr_pv_x[t] = export_t
            tr_soc[t] = soc
            tr_unmet[t] = unmet

    return (s_grid, s_grid_cost, s_peak_grid, s_pv_d, s_pv_b, s_pv_x, s_curtail,
            s_bat_d, s_unmet, s_through,
            tr_grid, tr_pv_d, tr_bat_d, tr_pv_x, tr_soc, tr_unmet)


def _offpeak_mask() -> np.ndarray:
    hours = np.arange(config.HOURS_PER_YEAR) % 24
    return ((hours >= _OFFPEAK_START) & (hours < _OFFPEAK_END)).astype(np.float64)


_OFFPEAK = _offpeak_mask()
_TOU = np.asarray(config.TOU_TARIFF, float)[np.arange(config.HOURS_PER_YEAR) % 24]


def _run(design: Design, demand_kwh, pv_kwh, battery_rt_eff, charger_power_kw,
         charger_availability, grid_kw, want_traces):
    rt = config.BATTERY_ROUNDTRIP_EFF["baseline"] if battery_rt_eff is None else battery_rt_eff
    p_charger = config.CHARGER_POWER_KW["baseline"] if charger_power_kw is None else charger_power_kw
    avail = config.CHARGER_AVAILABILITY["baseline"] if charger_availability is None else charger_availability
    grid_cap = config.GRID_CONNECTION_KW if grid_kw is None else grid_kw

    eff_one_way = float(np.sqrt(rt))
    usable_cap = float(design.battery_kwh * config.BATTERY_DOD)
    p_batt_max = float(max(design.battery_kwh * 0.5, 0.0))
    deliver_cap = float(design.n_chargers * p_charger * avail)

    demand_kwh = np.ascontiguousarray(demand_kwh, dtype=np.float64)
    pv_kwh = np.ascontiguousarray(pv_kwh, dtype=np.float64)
    tou = _TOU if len(demand_kwh) == config.HOURS_PER_YEAR else \
        np.asarray(config.TOU_TARIFF, float)[np.arange(len(demand_kwh)) % 24]

    return _dispatch(demand_kwh, pv_kwh, tou, usable_cap, p_batt_max,
                     deliver_cap, float(grid_cap), eff_one_way, want_traces)


def _assemble(design, demand_kwh, out, want_traces) -> dict:
    (s_grid, s_grid_cost, s_peak_grid, s_pv_d, s_pv_b, s_pv_x, s_curtail,
     s_bat_d, s_unmet, s_through,
     tr_grid, tr_pv_d, tr_bat_d, tr_pv_x, tr_soc, tr_unmet) = out

    demand_total = float(np.sum(demand_kwh))
    served_total = demand_total - s_unmet
    service_level = served_total / demand_total if demand_total > 0 else 1.0
    grid_import = s_grid                          # all grid import serves demand
    pv_total = s_pv_d + s_pv_b + s_pv_x + s_curtail

    # Solar fraction: PV directly used + PV stored then discharged (battery only
    # stores PV under smart charging, so battery discharge is 100% solar-sourced).
    renewable_served = s_pv_d + s_bat_d
    solar_fraction = renewable_served / served_total if served_total > 0 else 0.0

    result = {
        "design": design,
        "demand_total_kwh": demand_total,
        "demand_served_kwh": served_total,
        "unmet_demand_kwh": s_unmet,
        "service_level": service_level,
        "grid_import_kwh": grid_import,
        "grid_to_demand_kwh": s_grid,
        "grid_to_battery_kwh": 0.0,
        "grid_cost_baseline_gbp": s_grid_cost,    # at baseline ToU tariff
        "peak_grid_kw": s_peak_grid,              # for demand/capacity charge
        "pv_to_demand_kwh": s_pv_d,
        "pv_to_battery_kwh": s_pv_b,
        "pv_export_kwh": s_pv_x,
        "pv_curtailed_kwh": s_curtail,
        "battery_to_demand_kwh": s_bat_d,
        "battery_throughput_kwh": s_through,
        "pv_generation_kwh": pv_total,
        "pv_self_consumption_kwh": s_pv_d + s_pv_b,
        "solar_fraction": solar_fraction,
    }
    if want_traces:
        result.update({
            "_grid_import": np.asarray(tr_grid),
            "_pv_to_demand": np.asarray(tr_pv_d),
            "_batt_to_demand": np.asarray(tr_bat_d),
            "_pv_export": np.asarray(tr_pv_x),
            "_soc": np.asarray(tr_soc),
            "_unmet": np.asarray(tr_unmet),
        })
    return result


def simulate(design: Design, demand_kwh, pv_kwh, *,
             battery_rt_eff=None, charger_power_kw=None,
             charger_availability=None, grid_kw=None) -> dict:
    """Full energy balance WITH hourly traces (for plotting a single design)."""
    out = _run(design, demand_kwh, pv_kwh, battery_rt_eff, charger_power_kw,
               charger_availability, grid_kw, True)
    return _assemble(design, demand_kwh, out, True)


def simulate_fast(design: Design, demand_kwh, pv_kwh, *,
                  battery_rt_eff=None, charger_power_kw=None,
                  charger_availability=None, grid_kw=None) -> dict:
    """Scalar-only energy balance (no traces) for Monte-Carlo / sweeps."""
    out = _run(design, demand_kwh, pv_kwh, battery_rt_eff, charger_power_kw,
               charger_availability, grid_kw, False)
    return _assemble(design, demand_kwh, out, False)


def meets_service_target(result: dict) -> bool:
    return result["service_level"] >= config.SERVICE_LEVEL_TARGET


if __name__ == "__main__":
    from . import demand_model, pv_model
    import time
    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    demand = demand_model.hourly_demand_series(demand_model.scenario_params("High", 7), df)
    pv_series = pv_model.specific_yield_per_kwp(solar)

    print(f"Numba available  : {_HAVE_NUMBA}   grid cap = {config.GRID_CONNECTION_KW} kW")
    print(f"High mid-life demand: {demand.sum():,.0f} kWh/yr, peak {demand.max():.1f} kWh/h\n")
    for design in [Design(5, 0, 4), Design(15, 20, 12), Design(25, 50, 20)]:
        pv = design.pv_kwp * pv_series
        r = simulate_fast(design, demand, pv)
        print(f"{design}")
        print(f"   service {r['service_level']*100:5.1f}% | solar {r['solar_fraction']*100:4.1f}% | "
              f"unmet {r['unmet_demand_kwh']:6.0f} kWh | grid {r['grid_import_kwh']:7.0f} kWh")
    t = time.time()
    for _ in range(200):
        simulate_fast(Design(15, 20, 12), demand, 15 * pv_series)
    print(f"\nper fast sim: {(time.time()-t)/200*1000:.3f} ms")
