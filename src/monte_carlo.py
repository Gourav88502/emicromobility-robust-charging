"""
monte_carlo.py
==============
500-sample Monte-Carlo uncertainty fan (EoI methodology step 2).

Each sample draws the eight uncertain variables from triangular distributions
defined in config.UNCERTAIN_VARIABLES, builds the corresponding demand and PV
series, runs the fast energy balance for a given design and records cost,
service level and solar fraction. The spread of outcomes is the "demand fan"
and the basis for robust design metrics.
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config, demand_model, pv_model, economics
from .energy_balance import simulate_fast
from .economics import Design


@dataclass
class Sample:
    """One Monte-Carlo realisation of all uncertain inputs."""
    demand_intensity: float
    demand_growth: float
    fleet_utilisation: float
    trip_energy: float
    pv_output: float
    battery_eff: float
    charger_avail: float
    electricity_price: float
    equipment_cost: float


# Correlation of the three demand drivers with a shared latent "demand regime".
# A booming deployment tends to have high trips, high utilisation AND high growth
# together; a quiet one has all three low. This co-movement fattens the demand
# tail realistically (independent sampling would mask the worst-case corner).
DEMAND_REGIME_CORR = 0.55


def _triangular(rng, v) -> float:
    lo, mode, hi = v.low, v.baseline, v.high
    if lo == hi:
        return mode
    if not (lo <= mode <= hi):
        mode = min(max(mode, lo), hi)
    return float(rng.triangular(lo, mode, hi))


def _triangular_ppf(p: float, lo: float, mode: float, hi: float) -> float:
    """Inverse CDF of a triangular distribution (for correlated sampling)."""
    if hi <= lo:
        return lo
    mode = min(max(mode, lo), hi)
    c = (mode - lo) / (hi - lo)
    p = min(max(p, 0.0), 1.0)
    if p < c:
        return lo + np.sqrt(p * (hi - lo) * (mode - lo))
    return hi - np.sqrt((1 - p) * (hi - lo) * (hi - mode))


def draw_samples(n: int = config.N_MONTE_CARLO, seed: int = config.RANDOM_SEED,
                 correlated: bool = True) -> list[Sample]:
    """
    Draw n Monte-Carlo samples.

    correlated=True  : the three demand drivers co-move through a shared demand
                       regime (realistic; used for the uncertainty fan).
    correlated=False : all inputs independent (required for variance-based
                       global sensitivity / Sobol indices).
    """
    rng = np.random.default_rng(seed)
    var = {v.name: v for v in config.UNCERTAIN_VARIABLES}
    w = DEMAND_REGIME_CORR if correlated else 0.0

    def corr_draw(name: str, regime: float) -> float:
        v = var[name]
        p = w * regime + (1 - w) * rng.random()       # rank-correlated percentile
        return _triangular_ppf(p, v.low, v.baseline, v.high)

    out = []
    for _ in range(n):
        regime = rng.random()                          # shared demand-regime percentile
        out.append(Sample(
            demand_intensity=corr_draw("demand_intensity", regime),
            demand_growth=corr_draw("demand_growth", regime),
            fleet_utilisation=corr_draw("fleet_utilisation", regime),
            trip_energy=_triangular(rng, var["trip_energy"]),
            pv_output=_triangular(rng, var["pv_output"]),
            battery_eff=_triangular(rng, var["battery_eff"]),
            charger_avail=_triangular(rng, var["charger_avail"]),
            electricity_price=_triangular(rng, var["electricity_price"]),
            equipment_cost=_triangular(rng, var["equipment_cost"]),
        ))
    return out


def _demand_for_sample(s: Sample, df, year_index: int) -> np.ndarray:
    params = demand_model.DemandParams(
        trips_per_scooter_day=s.demand_intensity,
        fleet_utilisation=s.fleet_utilisation,
        trip_energy_wh_per_km=s.trip_energy,
        demand_growth=s.demand_growth,
        year_index=year_index,
    )
    return demand_model.hourly_demand_series(params, df)


def evaluate_design(design: Design,
                    samples: list[Sample],
                    df=None, solar=None,
                    year_index: int | None = None) -> pd.DataFrame:
    """Run every Monte-Carlo sample for one design; return a tidy results frame."""
    if df is None:
        df = demand_model.load_dft()
    if solar is None:
        solar = pv_model.load_solar()
    if year_index is None:
        year_index = config.OPTIMISATION_HORIZON_YEARS       # design horizon

    base_yield = pv_model.specific_yield_per_kwp(solar)
    rows = []
    for i, s in enumerate(samples):
        demand = _demand_for_sample(s, df, year_index)
        # s.pv_output is sampled as an absolute performance ratio; the base yield
        # series was built at baseline PR, so rescale by (sampled PR / baseline).
        pv = design.pv_kwp * base_yield * (s.pv_output / config.PV_PERFORMANCE_RATIO["baseline"])

        res = simulate_fast(design, demand, pv,
                            battery_rt_eff=s.battery_eff,
                            charger_availability=s.charger_avail)
        costs = economics.annual_costs(
            design, res,
            tariff=s.electricity_price,
            cost_multiplier=s.equipment_cost,
            battery_cost=config.BATTERY_CAPEX_PER_KWH["baseline"] * s.equipment_cost,
        )
        rows.append({
            "sample": i,
            "annual_cost": costs["total_annual_cost"],
            "capex": costs["capex_total"],
            "service_level": res["service_level"],
            "solar_fraction": res["solar_fraction"],
            "grid_import_kwh": res["grid_import_kwh"],
            "unmet_kwh": res["unmet_demand_kwh"],
            "demand_kwh": res["demand_total_kwh"],
        })
    return pd.DataFrame(rows)


def _bootstrap_ci(data: np.ndarray, stat_fn, n_boot: int = 2000,
                   seed: int = config.RANDOM_SEED, alpha: float = 0.05
                   ) -> tuple[float, float]:
    """
    Percentile bootstrap confidence interval for a scalar statistic.

    Returns (ci_lo, ci_hi) at the (alpha/2, 1-alpha/2) percentile of the
    bootstrap distribution — standard non-parametric CI, no normality assumed
    (Efron & Hastie, 2016; DiCiccio & Efron, 1996).
    """
    rng = np.random.default_rng(seed)
    boot_stats = np.array([
        stat_fn(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_boot)
    ])
    return float(np.percentile(boot_stats, 100 * alpha / 2)), \
           float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))


def summarise(results: pd.DataFrame, n_boot: int = 2000) -> dict:
    """
    Summarise Monte-Carlo results with bootstrap 95 % confidence intervals.

    Bootstrap CIs are computed on P05, P50, P95, and the probability of
    meeting the service target — the key robustness metrics.  This provides
    the statistical rigour required for academic reporting (Efron & Hastie,
    2016: 'Computer Age Statistical Inference', Ch. 10).

    n_boot : number of bootstrap replicates (2000 gives stable CIs for n=500).
    """
    cost   = results["annual_cost"].values
    svc    = results["service_level"].values

    q = results["annual_cost"].quantile([0.05, 0.5, 0.95])

    p05_lo, p05_hi = _bootstrap_ci(cost, lambda x: np.percentile(x, 5),  n_boot)
    p50_lo, p50_hi = _bootstrap_ci(cost, lambda x: np.percentile(x, 50), n_boot)
    p95_lo, p95_hi = _bootstrap_ci(cost, lambda x: np.percentile(x, 95), n_boot)
    pm_lo,  pm_hi  = _bootstrap_ci(
        (svc >= config.SERVICE_LEVEL_TARGET).astype(float),
        np.mean, n_boot)

    return {
        # Point estimates
        "cost_mean":        float(cost.mean()),
        "cost_p05":         float(q.loc[0.05]),
        "cost_p50":         float(q.loc[0.50]),
        "cost_p95":         float(q.loc[0.95]),
        "cost_std":         float(cost.std(ddof=1)),
        "service_mean":     float(svc.mean()),
        "service_p05":      float(results["service_level"].quantile(0.05)),
        "prob_meets_target": float((svc >= config.SERVICE_LEVEL_TARGET).mean()),
        "solar_fraction_mean": float(results["solar_fraction"].mean()),
        # Bootstrap 95 % confidence intervals (key academic addition)
        "ci_cost_p05":      (p05_lo, p05_hi),
        "ci_cost_p50":      (p50_lo, p50_hi),
        "ci_cost_p95":      (p95_lo, p95_hi),
        "ci_prob_meets":    (pm_lo,  pm_hi),
        "n_boot":           n_boot,
        "n_samples":        len(cost),
    }


if __name__ == "__main__":
    import time
    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    samples = draw_samples(config.N_MONTE_CARLO)
    design = Design(20, 30, 12)
    t = time.time()
    res = evaluate_design(design, samples, df, solar)
    print(f"{config.N_MONTE_CARLO} samples in {time.time()-t:.1f}s for {design}")
    s = summarise(res)
    print(f"  Annual cost P50  : GBP {s['cost_p50']:,.0f}  "
          f"(P05 {s['cost_p05']:,.0f} / P95 {s['cost_p95']:,.0f})")
    print(f"  Mean service     : {s['service_mean']*100:.1f}%  "
          f"(P(meet {config.SERVICE_LEVEL_TARGET*100:.0f}%) = {s['prob_meets_target']*100:.0f}%)")
    print(f"  Mean solar frac  : {s['solar_fraction_mean']*100:.1f}%")
