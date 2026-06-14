"""
route_energy.py  —  THEME 2
===========================
Charge/discharge profiles of e-bike batteries: PERSONAL vs SHARED, across
different driving routes.

This module delivers Theme 2 directly: it (1) estimates the battery energy a
ride draws as a physics-based function of the ROUTE (gradient, speed, stop-go)
and the rider's assist level, and (2) simulates the 24-hour battery
state-of-charge (SoC) of a privately-owned commuter e-bike versus a shared-scheme
e-bike. The two duty cycles are very different, which is exactly why a shared
fleet needs a managed charging hub (the Theme 3 link) while private owners charge
at home — and why their batteries age differently.

Energy model (Burani et al. 2022; Ouf et al. 2023):
    F  = m g (Crr + grade) + 0.5 rho Cd A v^2            [N]   tractive force
    E_wheel = F * 1000 / 3600                            [Wh/km] energy at the wheel
    + stop-go term  s * 0.5 m v^2  (no regen on most e-bikes)
    E_batt  = E_wheel * motor_share / eta_drive          [Wh/km] drawn from the pack
    E_grid  = E_batt / (eta_charger * sqrt(eta_roundtrip))[Wh/km] drawn from the grid
`motor_share` is the fraction of propulsion supplied by the motor (the rest is
the rider's legs), set by the pedal-assist (PAS) level.

Run standalone:  python -m src.route_energy
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from . import config

G = 9.81            # m/s^2
RHO = 1.225         # kg/m^3 air density
ETA_DRIVE = 0.78    # motor + controller + transmission efficiency
ETA_CHARGER = 0.92  # AC->DC charger efficiency


@dataclass
class Route:
    name: str
    grade: float        # average gradient (rise/run)
    speed_ms: float     # average speed (m/s)
    stops_per_km: float # stop-start events per km (urban congestion)
    cda: float = 0.7    # drag area Cd*A (upright rider)
    crr: float = 0.008  # rolling-resistance coefficient (tarmac)


# Representative routes around a campus / city scheme.
ROUTES = [
    Route("Flat urban",        0.000, 4.4, 3.0),
    Route("Hilly urban",       0.030, 4.0, 3.0),
    Route("Suburban commute",  0.010, 5.6, 1.2),
    Route("Campus short-hop",  0.000, 3.6, 4.0),
    Route("Cargo delivery",    0.015, 4.2, 2.5, cda=0.95, crr=0.012),
]


def energy_wh_per_km(route: Route, mass_kg: float, motor_share: float) -> dict:
    """Battery and grid energy per km for one route + rider/vehicle."""
    f_roll = mass_kg * G * route.crr
    f_grade = mass_kg * G * route.grade
    f_drag = 0.5 * RHO * route.cda * route.speed_ms ** 2
    e_wheel = (f_roll + f_grade + f_drag) * 1000.0 / 3600.0          # Wh/km
    # stop-go kinetic energy, not recovered (most e-bikes have no regen)
    e_stop = route.stops_per_km * 0.5 * mass_kg * route.speed_ms ** 2 * 1000.0 / 3600.0 / 1000.0
    e_wheel_total = e_wheel + e_stop
    e_batt = e_wheel_total * motor_share / ETA_DRIVE
    e_grid = e_batt / (ETA_CHARGER * config.BATTERY_ROUNDTRIP_EFF["baseline"] ** 0.5)
    return {"wheel": e_wheel_total, "battery": e_batt, "grid": e_grid}


# --------------------------------------------------------------------------- #
#  Two archetypes (Theme 2 comparison)
# --------------------------------------------------------------------------- #
def per_route_table() -> list[dict]:
    """Wh/km for each route, for a private commuter and a shared-scheme bike."""
    rows = []
    for r in ROUTES:
        # cargo route implies a heavier cargo bike + load; others ~ rider+bike
        if "Cargo" in r.name:
            mass, share = 150.0, 0.85
        else:
            mass, share = 105.0, 0.60
        e = energy_wh_per_km(r, mass, share)
        rows.append({"route": r.name, "wh_per_km_battery": round(e["battery"], 1),
                     "wh_per_km_grid": round(e["grid"], 1)})
    return rows


def soc_profiles(battery_wh: float | None = None) -> dict:
    """
    24-hour battery SoC (%) for a PERSONAL commuter e-bike and a SHARED e-bike.

    Personal: two longer assisted commute trips (≈8 km each) then a single deep
    overnight home charge -> one fairly deep cycle/day.
    Shared:   many short hops through the day (partial discharges) with shallow
    daytime opportunity top-ups and an overnight depot charge -> many shallow
    partial cycles/day (more throughput, gentler depth).
    """
    if battery_wh is None:
        battery_wh = config.BIKE_BATTERY_WH
    hours = np.arange(24)

    # per-km battery energy from the route model
    commute = energy_wh_per_km(ROUTES[2], 105.0, 0.60)["battery"]   # suburban commute
    # shared bikes mix flat, hilly and campus routes across many riders
    shared_pk = float(np.mean([energy_wh_per_km(ROUTES[i], 105.0, 0.60)["battery"]
                               for i in (0, 1, 3)]))

    # ---- personal commuter: 2 longer trips, single deep home charge -------- #
    p = np.full(24, 100.0)
    soc = 100.0
    trips_p = {8: 12.0, 18: 12.0}          # 12 km each way (24 km/day)
    charge_hours_p = {20, 21, 22, 23}      # plugged in at home in the evening
    for h in hours:
        if h in trips_p:
            soc -= 100.0 * trips_p[h] * commute / battery_wh
        if h in charge_hours_p:
            soc = min(100.0, soc + 25.0)   # ~2 A home charge ≈ 25%/h
        p[h] = max(0.0, soc)

    # ---- shared scheme bike: many riders, ~40 km/day, depot charging ------- #
    s = np.full(24, 100.0)
    soc = 100.0
    hop_km = np.array([0,0,0,0,0,0, 1.5,3.0,3.5,2.5,2.0,2.5,
                       3.0,2.5,2.0,2.5,3.5,4.0, 3.0,2.0,1.0,0,0,0], float)  # ~40 km/day
    for h in hours:
        soc -= 100.0 * hop_km[h] * shared_pk / battery_wh
        # shallow daytime opportunity top-up when docked & sunny (11-15h)
        if 11 <= h <= 15 and soc < 70:
            soc = min(72.0, soc + 6.0)
        # overnight depot charge back to full
        if h in (1, 2, 3, 4):
            soc = min(100.0, soc + 25.0)
        s[h] = max(0.0, soc)

    # duty-cycle / degradation metrics (equivalent full cycles per year)
    daily_throughput_p = sum(trips_p.values()) * commute            # Wh/day
    daily_throughput_s = hop_km.sum() * shared_pk
    efc_p = daily_throughput_p / battery_wh * 365.0
    efc_s = daily_throughput_s / battery_wh * 365.0
    return {
        "hours": hours.tolist(),
        "personal_soc": [round(x, 1) for x in p],
        "shared_soc": [round(x, 1) for x in s],
        "personal_min_soc": round(float(p.min()), 1),
        "shared_min_soc": round(float(s.min()), 1),
        "personal_efc_per_yr": round(efc_p, 0),
        "shared_efc_per_yr": round(efc_s, 0),
        "personal_daily_wh": round(daily_throughput_p, 0),
        "shared_daily_wh": round(daily_throughput_s, 0),
    }


def analyse() -> dict:
    table = per_route_table()
    prof = soc_profiles()
    grids = [r["wh_per_km_grid"] for r in table]
    return {
        "per_route": table,
        "wh_per_km_grid_min": min(grids),
        "wh_per_km_grid_max": max(grids),
        "fleet_mean_wh_per_km_grid": round(float(np.mean(grids)), 1),
        "profiles": prof,
    }


def make_figure(out_png) -> str:
    """Two-panel Theme-2 figure: per-route Wh/km bars + 24-h SoC profiles."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = analyse()
    NAVY, BLUE, ORANGE, GREEN = "#1B1B3A", "#2E86AB", "#E07B39", "#2E7D46"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.7))

    # left: battery Wh/km by route
    names = [r["route"] for r in res["per_route"]]
    vals = [r["wh_per_km_battery"] for r in res["per_route"]]
    ax1.barh(names, vals, color=[ORANGE if "Cargo" in n else BLUE for n in names])
    for i, v in enumerate(vals):
        ax1.text(v + 0.2, i, f"{v:g}", va="center", fontsize=9, color=NAVY)
    ax1.set_xlabel("Battery energy use (Wh/km)")
    ax1.set_title("(a) Energy per km by route & vehicle (physics model)",
                  fontsize=10, color=NAVY)
    ax1.invert_yaxis()
    ax1.grid(axis="x", alpha=0.25)

    # right: 24-h SoC profiles
    pr = res["profiles"]
    h = pr["hours"]
    ax2.plot(h, pr["personal_soc"], color=NAVY, lw=2.2, marker="o", ms=3,
             label=f"Personal commuter ({pr['personal_efc_per_yr']:.0f} EFC/yr)")
    ax2.plot(h, pr["shared_soc"], color=GREEN, lw=2.2, marker="s", ms=3,
             label=f"Shared scheme ({pr['shared_efc_per_yr']:.0f} EFC/yr)")
    ax2.axhline(20, color="#c33", ls="--", lw=1, alpha=0.7)
    ax2.text(0.3, 22, "20% reserve", color="#c33", fontsize=7.5)
    ax2.set_xlabel("Hour of day"); ax2.set_ylabel("Battery state of charge (%)")
    ax2.set_ylim(0, 105); ax2.set_xlim(0, 23)
    ax2.set_title("(b) Charge/discharge profile: personal vs shared",
                  fontsize=10, color=NAVY)
    ax2.legend(fontsize=8, loc="lower left"); ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(str(out_png), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_png)


def make_figure_compact(out_png) -> str:
    """Single-panel personal-vs-shared SoC profile (for the 2-page summary)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pr = soc_profiles()
    NAVY, GREEN = "#1B1B3A", "#2E7D46"
    fig, ax = plt.subplots(figsize=(5.4, 3.3))
    h = pr["hours"]
    ax.plot(h, pr["personal_soc"], color=NAVY, lw=2.4, marker="o", ms=3,
            label=f"Personal e-bike ({pr['personal_efc_per_yr']:.0f} cycles/yr)")
    ax.plot(h, pr["shared_soc"], color=GREEN, lw=2.4, marker="s", ms=3,
            label=f"Shared e-bike ({pr['shared_efc_per_yr']:.0f} cycles/yr)")
    ax.axhline(20, color="#c33", ls="--", lw=1, alpha=0.7)
    ax.set_xlabel("Hour of day"); ax.set_ylabel("Battery state of charge (%)")
    ax.set_ylim(0, 105); ax.set_xlim(0, 23)
    ax.legend(fontsize=8.5, loc="lower left"); ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(str(out_png), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_png)


if __name__ == "__main__":
    r = analyse()
    print("Theme 2 — battery energy by route (Wh/km, grid):")
    for row in r["per_route"]:
        print(f"  {row['route']:18s} battery {row['wh_per_km_battery']:5.1f} | "
              f"grid {row['wh_per_km_grid']:5.1f}")
    print(f"  fleet-mean grid: {r['fleet_mean_wh_per_km_grid']} Wh/km")
    p = r["profiles"]
    print(f"\nPersonal: min SoC {p['personal_min_soc']}% | {p['personal_efc_per_yr']:.0f} EFC/yr")
    print(f"Shared  : min SoC {p['shared_min_soc']}% | {p['shared_efc_per_yr']:.0f} EFC/yr")
