"""
optimization.py
================
Robust charging-station design (EoI methodology steps 3-4).

Decision space  : every (PV kWp, battery kWh, charger count) in config.
Scenario space  : a structured set of demand scenarios spanning the uncertainty
                  (demand growth x fleet utilisation x trip energy), evaluated at
                  a mid-life horizon.

Four design rules are compared:

  * Deterministic (naive)  - optimise for the single Medium/average scenario.
  * Stochastic programming - minimise probability-weighted expected cost.
  * Minimax regret         - minimise the worst-case regret across scenarios.
  * Maximin (robust worst) - minimise the worst-case absolute cost.

The "value of robustness" is the reduction in worst-case cost achieved by the
robust design relative to the naive design.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from itertools import product

import numpy as np
import pandas as pd

from . import config, demand_model, pv_model, economics
from .energy_balance import simulate_fast, meets_service_target
from .economics import Design


# --------------------------------------------------------------------------- #
#  Scenario construction
# --------------------------------------------------------------------------- #
@dataclass
class Scenario:
    name: str
    demand_level: str
    trips_per_scooter_day: float
    fleet_utilisation: float
    demand_growth: float
    probability: float
    demand_kwh: np.ndarray = field(repr=False, default=None)


def build_scenarios(df=None, year_index: int | None = None) -> list[Scenario]:
    """
    Structured demand scenario set spanning the EoI Low/Medium/High framing.

    Axes: demand level (trips/scooter/day x fleet utilisation, the primary
    lever) x year-on-year demand growth, evaluated at a mid-life horizon.
    3 levels x 3 growth rates = 9 interpretable scenarios with
    literature-based probability weights (central outcomes more likely).
    """
    if df is None:
        df = demand_model.load_dft()
    if year_index is None:
        year_index = config.OPTIMISATION_HORIZON_YEARS

    levels = {
        "Low":    (config.TRIPS_PER_SCOOTER_DAY["low"], config.FLEET_UTILISATION["low"]),
        "Medium": (config.TRIPS_PER_SCOOTER_DAY["medium"], config.FLEET_UTILISATION["baseline"]),
        "High":   (config.TRIPS_PER_SCOOTER_DAY["high"], config.FLEET_UTILISATION["high"]),
    }
    growth = {"low": config.DEMAND_GROWTH["low"], "med": config.DEMAND_GROWTH["medium"],
              "high": config.DEMAND_GROWTH["high"]}
    w_level = {"Low": 0.25, "Medium": 0.50, "High": 0.25}
    w_growth = {"low": 0.25, "med": 0.50, "high": 0.25}

    scenarios = []
    for lname, (tpd, util) in levels.items():
        for gk, gv in growth.items():
            params = demand_model.DemandParams(
                trips_per_scooter_day=tpd, fleet_utilisation=util,
                trip_energy_wh_per_km=config.TRIP_ENERGY_WH_PER_KM["baseline"],
                demand_growth=gv, year_index=year_index)
            scenarios.append(Scenario(
                name=f"{lname}/growth:{gk}", demand_level=lname,
                trips_per_scooter_day=tpd, fleet_utilisation=util,
                demand_growth=gv, probability=w_level[lname] * w_growth[gk],
                demand_kwh=demand_model.hourly_demand_series(params, df)))
    total_p = sum(s.probability for s in scenarios)
    for s in scenarios:
        s.probability /= total_p
    return scenarios


def all_designs() -> list[Design]:
    return [Design(pv, batt, ch)
            for pv in config.PV_SIZES_KWP
            for batt in config.BATTERY_SIZES_KWH
            for ch in config.CHARGER_COUNTS]


# --------------------------------------------------------------------------- #
#  Cost matrix
# --------------------------------------------------------------------------- #
def cost_matrix(designs: list[Design], scenarios: list[Scenario],
                solar=None) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (cost[D x S], service[D x S]) annual cost and service-level matrices.
    """
    if solar is None:
        solar = pv_model.load_solar()
    base_yield = pv_model.specific_yield_per_kwp(solar)

    nD, nS = len(designs), len(scenarios)
    cost = np.zeros((nD, nS))
    service = np.zeros((nD, nS))

    # Cache PV generation per pv_kwp (PV output held at baseline across scenarios).
    pv_cache = {pv: pv * base_yield for pv in config.PV_SIZES_KWP}

    for i, d in enumerate(designs):
        pv = pv_cache[d.pv_kwp]
        for j, s in enumerate(scenarios):
            res = simulate_fast(d, s.demand_kwh, pv)
            costs = economics.annual_costs(d, res)
            cost[i, j] = costs["total_annual_cost"]
            service[i, j] = res["service_level"]
    return cost, service


# --------------------------------------------------------------------------- #
#  Decision rules
# --------------------------------------------------------------------------- #
def robustly_feasible_mask(service: np.ndarray) -> np.ndarray:
    """A design is robustly feasible if it meets the service target in EVERY scenario."""
    return (service >= config.SERVICE_LEVEL_TARGET).all(axis=1)


def solve(designs: list[Design], scenarios: list[Scenario],
          cost: np.ndarray, service: np.ndarray) -> dict:
    """
    Apply the four decision rules. Unmet demand is priced into `cost` as a soft
    penalty (config.UNMET_DEMAND_PENALTY), so the rules trade capital against the
    risk of stranding the fleet — no hard feasibility masking is required, which
    lets each rule select a genuinely different design.
    """
    probs = np.array([s.probability for s in scenarios])

    # Best achievable cost in each scenario over ALL designs -> regret reference.
    best_per_scenario = cost.min(axis=0)
    regret = cost - best_per_scenario[None, :]

    expected_cost = (cost * probs[None, :]).sum(axis=1)     # expected total cost
    worst_cost = cost.max(axis=1)                            # maximin objective
    max_regret = regret.max(axis=1)                          # minimax-regret objective

    robust_feasible = robustly_feasible_mask(service)
    medium_idx = next(i for i, s in enumerate(scenarios)
                      if s.demand_level == "Medium"
                      and abs(s.demand_growth - config.DEMAND_GROWTH["medium"]) < 1e-9)
    feasible_in_medium = service[:, medium_idx] >= config.SERVICE_LEVEL_TARGET

    # Probability mass of scenarios each design serves at/above the target.
    served_ok = service >= config.SERVICE_LEVEL_TARGET
    prob_served = (served_ok * probs[None, :]).sum(axis=1)

    # The naive planner sizes for the single central scenario only.
    naive_candidates = np.where(feasible_in_medium, cost[:, medium_idx], np.inf)
    naive_idx = int(np.argmin(naive_candidates))

    # Chance-constrained stochastic program: min expected cost s.t. the service
    # target is met in scenarios totalling >= beta probability.
    chance_ok = prob_served >= config.CHANCE_CONSTRAINT_BETA - 1e-9
    stoch_candidates = np.where(chance_ok, expected_cost, np.inf)
    stochastic_idx = int(np.argmin(stoch_candidates)) if chance_ok.any() \
        else int(np.argmin(expected_cost))

    rules = {
        "naive_deterministic": naive_idx,
        "stochastic": stochastic_idx,
        "minimax_regret": int(np.argmin(max_regret)),
        "maximin_robust": int(np.argmin(worst_cost)),
    }

    out = {"robust_feasible_count": int(robust_feasible.sum()),
           "n_designs": len(designs), "n_scenarios": len(scenarios),
           "rules": {}}
    for rule, idx in rules.items():
        out["rules"][rule] = {
            "design": designs[idx],
            "index": idx,
            "expected_cost": float(expected_cost[idx]),
            "worst_cost": float(worst_cost[idx]),
            "max_regret": float(max_regret[idx]),
            "mean_service": float(service[idx].mean()),
            "min_service": float(service[idx].min()),
            "prob_served": float(prob_served[idx]),
            "robustly_feasible": bool(robust_feasible[idx]),
        }

    # Value of robustness compares the naive design with the recommended robust
    # design (maximin — the only fully robustly-feasible rule).
    naive = out["rules"]["naive_deterministic"]
    robust = out["rules"]["maximin_robust"]
    out["recommended_rule"] = "maximin_robust"
    out["value_of_robustness"] = {
        "naive_worst_cost": naive["worst_cost"],
        "robust_worst_cost": robust["worst_cost"],
        "worst_cost_reduction": naive["worst_cost"] - robust["worst_cost"],
        "worst_cost_reduction_pct": (
            (naive["worst_cost"] - robust["worst_cost"]) / naive["worst_cost"] * 100
            if naive["worst_cost"] > 0 else 0.0),
        "naive_min_service": naive["min_service"],
        "robust_min_service": robust["min_service"],
        "naive_max_regret": naive["max_regret"],
        "robust_max_regret": robust["max_regret"],
    }
    out["_cost"] = cost
    out["_service"] = service
    out["_feasible"] = robust_feasible
    out["_expected_cost"] = expected_cost
    out["_worst_cost"] = worst_cost
    out["_max_regret"] = max_regret
    out["_designs"] = designs
    out["_scenarios"] = scenarios
    return out


# --------------------------------------------------------------------------- #
#  Pareto frontier (cost vs robustness)
# --------------------------------------------------------------------------- #
def pareto_frontier(designs, expected_cost, worst_cost, feasible) -> pd.DataFrame:
    """Non-dominated set in (expected cost, worst-case cost) space, all designs."""
    pts = sorted(range(len(designs)), key=lambda i: expected_cost[i])
    frontier, best_worst = [], np.inf
    for i in pts:
        if worst_cost[i] < best_worst - 1e-9:
            frontier.append(i)
            best_worst = worst_cost[i]
    d = designs
    return pd.DataFrame([{
        "index": i, "design": str(d[i]), "pv_kwp": d[i].pv_kwp,
        "battery_kwh": d[i].battery_kwh, "n_chargers": d[i].n_chargers,
        "expected_cost": expected_cost[i], "worst_cost": worst_cost[i],
        "robustly_feasible": bool(feasible[i]),
    } for i in frontier])


def run_full_optimisation(df=None, solar=None, year_index: int | None = None) -> dict:
    designs = all_designs()
    scenarios = build_scenarios(df, year_index)
    cost, service = cost_matrix(designs, scenarios, solar)
    result = solve(designs, scenarios, cost, service)
    result["pareto"] = pareto_frontier(
        designs, result["_expected_cost"], result["_worst_cost"], result["_feasible"])
    return result


if __name__ == "__main__":
    import time
    t = time.time()
    r = run_full_optimisation()
    print(f"Optimised {r['n_designs']} designs x {r['n_scenarios']} scenarios "
          f"in {time.time()-t:.1f}s  ({r['robust_feasible_count']} robustly feasible)\n")
    for rule, info in r["rules"].items():
        flag = "OK" if info["robustly_feasible"] else "FAILS high demand"
        print(f"  {rule:22s}: {info['design']}  [{flag}]")
        print(f"  {'':22s}  worst GBP {info['worst_cost']:,.0f}/yr | "
              f"E[cost] GBP {info['expected_cost']:,.0f}/yr | "
              f"max-regret GBP {info['max_regret']:,.0f} | "
              f"min-service {info['min_service']*100:.1f}%")
    v = r["value_of_robustness"]
    print(f"\nValue of robustness: worst-case cost cut by "
          f"GBP {v['worst_cost_reduction']:,.0f}/yr "
          f"({v['worst_cost_reduction_pct']:.1f}%) vs naive design")
    print(f"Pareto frontier has {len(r['pareto'])} non-dominated designs")
