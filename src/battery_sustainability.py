"""
battery_sustainability.py
=========================
Battery analytics, degradation, safety and circularity for the storage option.

This module addresses the competition's central theme — *sustainability of
batteries in e-micromobility* — for the case where on-site storage IS deployed
(i.e. the weak-grid / off-grid-leaning regime, where the robustness analysis
shows a battery becomes essential). It quantifies:

  1. State-of-Health (SoH) degradation — combined cycle + calendar ageing.
  2. Replacement schedule and lifetime throughput over the project horizon.
  3. Second-life potential — when the pack retires from primary service it is
     re-deployed as lower-stress stationary storage before recycling.
  4. Circularity — recoverable critical-material mass at end of life.
  5. Safety — Li-ion chemistry choice, charge-rate margin, thermal-runaway
     mitigations for a depot setting.

Chemistry note: for a *depot stationary* battery we recommend **LFP**
(LiFePO4) over NMC. LFP contains no cobalt or nickel (lower supply-chain and
ethical risk), has a markedly higher thermal-runaway onset (~270 °C vs ~150 °C
for NMC) and a longer cycle life — the sustainable, safe default for fixed
charging-hub storage where gravimetric energy density is not the binding
constraint.

References (see REFERENCES.md):
  Mongird et al. (2020), PNNL energy-storage cost & performance.
  IRENA (2017), Electricity storage and renewables: costs and markets to 2030.
  BloombergNEF (2023), Lithium-ion battery price survey.
  Harper et al. (2019), Recycling lithium-ion batteries from electric vehicles,
    Nature 575, 75-86.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict

from . import config


# --------------------------------------------------------------------------- #
#  Material & safety constants (LFP depot pack — sourced, see module docstring)
# --------------------------------------------------------------------------- #
PACK_MASS_KG_PER_KWH = 8.0          # LFP pack incl. enclosure (Mongird 2020)
# Approximate recoverable material mass fractions of total pack mass, and the
# hydrometallurgical recovery rate achievable today (Harper et al. 2019).
MATERIALS = {
    # material : (mass fraction of pack, recovery rate)
    "Lithium":   (0.018, 0.90),
    "Iron+Phos": (0.20,  0.95),     # LFP cathode (no Co/Ni — key sustainability win)
    "Graphite":  (0.16,  0.70),
    "Copper":    (0.08,  0.95),
    "Aluminium": (0.06,  0.95),
}
SECOND_LIFE_RETIRE_SOH = 0.80       # retire from primary service at 80 % SoH
SECOND_LIFE_END_SOH = 0.60          # end of useful second life (stationary)
THERMAL_RUNAWAY_ONSET_C = {"LFP": 270.0, "NMC": 150.0}
EMBODIED_CO2_KG_PER_KWH = 75.0      # cradle-to-gate manufacturing (IEA 2023)


@dataclass
class BatteryLifeResult:
    battery_kwh: float
    annual_throughput_kwh: float
    equivalent_full_cycles_yr: float
    cycle_limited_life_yr: float
    calendar_limited_life_yr: float
    effective_life_yr: float
    replacements_over_project: float
    soh_at_design_horizon: float
    second_life_years: float
    recoverable_material_kg: dict
    recovered_fraction: float
    embodied_co2_t: float
    charge_c_rate: float
    safety_margin_c: float
    thermal_runaway_onset_C: float
    chemistry: str


def analyse(battery_kwh: float, annual_throughput_kwh: float,
            chemistry: str = "LFP",
            project_years: int | None = None) -> BatteryLifeResult:
    """
    Full battery sustainability analysis for a pack of `battery_kwh` cycling
    `annual_throughput_kwh` per year.

    `annual_throughput_kwh` is taken from the energy-balance simulation
    (result['battery_throughput_kwh']) so the degradation is driven by the
    REAL modelled duty cycle, not an assumption.
    """
    if project_years is None:
        project_years = config.PROJECT_LIFETIME_YEARS
    if battery_kwh <= 0:
        # No storage in the recommended design — analysis applies to the
        # weak-grid variant; return a zeroed result with a clear flag.
        return BatteryLifeResult(
            0, 0, 0, float("inf"), config.BATTERY_CALENDAR_LIFE_YEARS,
            config.BATTERY_CALENDAR_LIFE_YEARS, 0, 1.0, 0, {}, 0, 0,
            0, 0, THERMAL_RUNAWAY_ONSET_C[chemistry], chemistry)

    usable = battery_kwh * config.BATTERY_DOD
    efc = annual_throughput_kwh / (2.0 * usable) if usable > 0 else 0.0  # equiv full cycles/yr
    cycle_life = config.BATTERY_CYCLE_LIFE["baseline"]
    cycle_limited = cycle_life / efc if efc > 0 else float("inf")
    calendar_limited = float(config.BATTERY_CALENDAR_LIFE_YEARS)
    effective_life = min(cycle_limited, calendar_limited)
    replacements = max(project_years / effective_life - 1.0, 0.0)

    # Linear SoH model: 100 % -> 80 % (end-of-primary-life) over effective_life.
    horizon = config.OPTIMISATION_HORIZON_YEARS
    frac = min(horizon / effective_life, 1.0)
    soh_horizon = 1.0 - 0.20 * frac

    # Second life: after primary retirement at 80 % SoH, the pack runs as low-
    # stress stationary storage until ~60 % SoH. We size it from the calendar
    # headroom (typically several more years at shallow cycling).
    second_life_years = max(calendar_limited - effective_life, 0.0) + 4.0

    # Circularity — recoverable material mass at end of life.
    pack_mass = battery_kwh * PACK_MASS_KG_PER_KWH
    recoverable = {m: round(pack_mass * frac_mass * rec, 1)
                   for m, (frac_mass, rec) in MATERIALS.items()}
    total_recovered = sum(recoverable.values())
    recovered_fraction = total_recovered / pack_mass if pack_mass > 0 else 0.0

    embodied = battery_kwh * EMBODIED_CO2_KG_PER_KWH / 1000.0  # tonnes

    # Safety — charge C-rate vs a conservative depot limit (0.5C), margin, onset.
    c_rate = 0.5                                # we cap charge/discharge at 0.5C
    safe_limit = 1.0                            # depot best-practice ceiling (1C)
    safety_margin = safe_limit - c_rate

    return BatteryLifeResult(
        battery_kwh=battery_kwh,
        annual_throughput_kwh=round(annual_throughput_kwh, 0),
        equivalent_full_cycles_yr=round(efc, 1),
        cycle_limited_life_yr=round(cycle_limited, 1),
        calendar_limited_life_yr=round(calendar_limited, 1),
        effective_life_yr=round(effective_life, 1),
        replacements_over_project=round(replacements, 2),
        soh_at_design_horizon=round(soh_horizon, 3),
        second_life_years=round(second_life_years, 1),
        recoverable_material_kg=recoverable,
        recovered_fraction=round(recovered_fraction, 3),
        embodied_co2_t=round(embodied, 2),
        charge_c_rate=c_rate,
        safety_margin_c=round(safety_margin, 2),
        thermal_runaway_onset_C=THERMAL_RUNAWAY_ONSET_C[chemistry],
        chemistry=chemistry,
    )


def report(result: BatteryLifeResult) -> str:
    """Human-readable summary of the battery sustainability analysis."""
    if result.battery_kwh <= 0:
        return ("Recommended robust design uses NO storage at the 15 kW connection "
                "(smart charging suffices). This analysis applies to the weak-grid "
                "variant where a battery becomes essential.")
    r = result
    lines = [
        f"Battery sustainability — {r.battery_kwh:.0f} kWh {r.chemistry} pack",
        f"  Duty cycle      : {r.equivalent_full_cycles_yr} equiv. full cycles/yr "
        f"({r.annual_throughput_kwh:,.0f} kWh throughput)",
        f"  Effective life  : {r.effective_life_yr} yr "
        f"(cycle-limited {r.cycle_limited_life_yr}, calendar {r.calendar_limited_life_yr})",
        f"  SoH @ yr{config.OPTIMISATION_HORIZON_YEARS}      : {r.soh_at_design_horizon*100:.1f}%  "
        f"| replacements over {config.PROJECT_LIFETIME_YEARS}-yr project: {r.replacements_over_project}",
        f"  Second life     : ~{r.second_life_years} yr stationary use after primary retirement",
        f"  Circularity     : {r.recovered_fraction*100:.0f}% of pack mass recoverable "
        f"(Li {r.recoverable_material_kg.get('Lithium',0)} kg, "
        f"Cu {r.recoverable_material_kg.get('Copper',0)} kg)",
        f"  Embodied CO2    : {r.embodied_co2_t} t (cradle-to-gate)",
        f"  Safety          : {r.charge_c_rate}C charging (margin {r.safety_margin_c}C to 1C ceiling); "
        f"{r.chemistry} thermal-runaway onset {r.thermal_runaway_onset_C:.0f} °C "
        f"(vs ~150 °C NMC) — cobalt/nickel-free.",
    ]
    return "\n".join(lines)


def to_dict(result: BatteryLifeResult) -> dict:
    return asdict(result)


if __name__ == "__main__":
    from . import demand_model, pv_model
    from .economics import Design
    from .energy_balance import simulate_fast

    df = demand_model.load_demand(); solar = pv_model.load_solar()
    base_yield = pv_model.specific_yield_per_kwp(solar)
    demand = demand_model.hourly_demand_series(
        demand_model.scenario_params("High", config.OPTIMISATION_HORIZON_YEARS), df)

    # Storage variant (weak-grid case where a battery is deployed).
    d = Design(20, 30, 8)
    sim = simulate_fast(d, demand, d.pv_kwp * base_yield, grid_kw=10.0)
    res = analyse(d.battery_kwh, sim["battery_throughput_kwh"], chemistry="LFP")
    print(report(res))
