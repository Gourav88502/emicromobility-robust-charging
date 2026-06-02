"""
economics.py
============
Techno-economic engine: CAPEX, OPEX, battery replacement, levelised cost of
energy (LCOE), net present value (NPV) and total cost of ownership (TCO).

All cost benchmarks come from src/config.py (BEIS, IRENA, BloombergNEF, OZEV,
Zap-Map, Solar Trade Association). Every figure is therefore traceable.
"""

from __future__ import annotations
from dataclasses import dataclass

from . import config


@dataclass
class Design:
    """A candidate charging-station specification (the decision variables)."""
    pv_kwp: float
    battery_kwh: float
    n_chargers: int

    def __str__(self) -> str:
        return f"PV={self.pv_kwp:g}kWp | BESS={self.battery_kwh:g}kWh | {self.n_chargers} chargers"

    @property
    def key(self) -> tuple:
        return (self.pv_kwp, self.battery_kwh, self.n_chargers)


def capex(design: Design,
          pv_cost: float | None = None,
          battery_cost: float | None = None,
          charger_cost: float | None = None,
          install_frac: float | None = None,
          cost_multiplier: float = 1.0) -> dict:
    """Capital cost breakdown (GBP). cost_multiplier scales all equipment for MC."""
    pv_cost = config.PV_CAPEX_PER_KWP["baseline"] if pv_cost is None else pv_cost
    battery_cost = config.BATTERY_CAPEX_PER_KWH["baseline"] if battery_cost is None else battery_cost
    charger_cost = config.CHARGER_CAPEX_PER_UNIT["baseline"] if charger_cost is None else charger_cost
    install_frac = config.INSTALL_FRACTION["baseline"] if install_frac is None else install_frac

    pv = design.pv_kwp * pv_cost * cost_multiplier
    bess = design.battery_kwh * battery_cost * cost_multiplier
    chargers = design.n_chargers * charger_cost * cost_multiplier
    equipment = pv + bess + chargers
    install = equipment * install_frac
    total = equipment + install
    return {"pv": pv, "battery": bess, "chargers": chargers,
            "equipment": equipment, "installation": install, "total": total}


def annual_battery_replacement_cost(design: Design,
                                    annual_throughput_kwh: float,
                                    battery_cost: float | None = None,
                                    cycle_life: int | None = None) -> float:
    """Amortised battery replacement cost (GBP/yr) from energy throughput."""
    if design.battery_kwh <= 0:
        return 0.0
    battery_cost = config.BATTERY_CAPEX_PER_KWH["baseline"] if battery_cost is None else battery_cost
    cycle_life = config.BATTERY_CYCLE_LIFE["baseline"] if cycle_life is None else cycle_life
    usable = design.battery_kwh * config.BATTERY_DOD
    if usable <= 0:
        return 0.0
    equivalent_full_cycles = annual_throughput_kwh / usable
    fraction_of_life_per_year = equivalent_full_cycles / cycle_life
    return design.battery_kwh * battery_cost * fraction_of_life_per_year


def annuity_factor(rate: float, years: int) -> float:
    """Capital recovery factor that turns a present cost into an annual payment."""
    if rate <= 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def annual_costs(design: Design,
                 energy: dict,
                 *,
                 pv_cost=None, battery_cost=None, charger_cost=None,
                 install_frac=None, opex_frac=None, tariff=None,
                 cycle_life=None, cost_multiplier=1.0) -> dict:
    """
    Full annualised cost of ownership for one design under one energy result.

    `energy` must contain: grid_import_kwh, pv_export_kwh, unmet_demand_kwh,
    battery_throughput_kwh.
    """
    opex_frac = config.OPEX_FRACTION["baseline"] if opex_frac is None else opex_frac
    tariff = config.ELECTRICITY_TARIFF["baseline"] if tariff is None else tariff

    cap = capex(design, pv_cost, battery_cost, charger_cost, install_frac, cost_multiplier)
    crf = annuity_factor(config.DISCOUNT_RATE, config.PROJECT_LIFETIME_YEARS)
    annualised_capex = cap["total"] * crf

    fixed_om = cap["total"] * opex_frac
    battery_repl = annual_battery_replacement_cost(
        design, energy.get("battery_throughput_kwh", 0.0), battery_cost, cycle_life)
    grid_cost = energy.get("grid_import_kwh", 0.0) * tariff
    export_credit = energy.get("pv_export_kwh", 0.0) * config.FEED_IN_TARIFF
    unmet_penalty = energy.get("unmet_demand_kwh", 0.0) * config.UNMET_DEMAND_PENALTY

    total_annual = (annualised_capex + fixed_om + battery_repl
                    + grid_cost - export_credit + unmet_penalty)
    return {
        "capex_total": cap["total"],
        "annualised_capex": annualised_capex,
        "fixed_om": fixed_om,
        "battery_replacement": battery_repl,
        "grid_cost": grid_cost,
        "export_credit": export_credit,
        "unmet_penalty": unmet_penalty,
        "total_annual_cost": total_annual,
        "capex_breakdown": cap,
    }


def lcoe(design: Design, energy: dict, **kwargs) -> float:
    """Levelised cost of energy served (GBP/kWh)."""
    costs = annual_costs(design, energy, **kwargs)
    served = max(energy.get("demand_served_kwh", 0.0), 1e-6)
    return costs["total_annual_cost"] / served


if __name__ == "__main__":
    d = Design(pv_kwp=15, battery_kwh=30, n_chargers=12)
    e = {"grid_import_kwh": 40000, "pv_export_kwh": 5000, "unmet_demand_kwh": 200,
         "battery_throughput_kwh": 9000, "demand_served_kwh": 60000}
    c = annual_costs(d, e)
    print(d)
    print(f"  CAPEX total      : GBP {c['capex_total']:,.0f}")
    print(f"  Annual cost      : GBP {c['total_annual_cost']:,.0f}")
    print(f"  LCOE             : GBP {lcoe(d, e):.3f}/kWh")
