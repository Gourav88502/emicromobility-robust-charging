"""
pv_model.py
===========
Converts the calibrated PVGIS hourly specific-yield series (kWh per kWp) into an
8,760-hour generation profile for any PV array size, scaling for the chosen
performance ratio so it can be sampled in Monte Carlo / sensitivity runs.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from . import config

_BASE_PR = config.PV_PERFORMANCE_RATIO["baseline"]


def load_solar() -> pd.DataFrame:
    path = config.DATA_DIR / "pvgis_warwick_hourly.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. Run `python scripts/prepare_data.py` first.")
    return pd.read_csv(path, parse_dates=["datetime"])


def specific_yield_per_kwp(solar: pd.DataFrame | None = None) -> np.ndarray:
    """Baseline kWh-per-kWp hourly vector (length 8,760)."""
    if solar is None:
        solar = load_solar()
    return solar["pv_kWh_per_kWp"].to_numpy(dtype=float)


def pv_generation(pv_kwp: float,
                  performance_ratio: float | None = None,
                  output_multiplier: float = 1.0,
                  solar: pd.DataFrame | None = None) -> np.ndarray:
    """
    Hourly PV generation (kWh) for an array of `pv_kwp`.

    performance_ratio overrides the baseline PR (data already built at baseline
    PR, so we rescale by pr/baseline). output_multiplier applies Monte-Carlo
    year-to-year / soiling variability.
    """
    base = specific_yield_per_kwp(solar)
    pr = _BASE_PR if performance_ratio is None else performance_ratio
    scale = (pr / _BASE_PR) * output_multiplier
    return pv_kwp * base * scale


def annual_yield(pv_kwp: float, **kwargs) -> float:
    return float(pv_generation(pv_kwp, **kwargs).sum())


if __name__ == "__main__":
    solar = load_solar()
    sy = specific_yield_per_kwp(solar).sum()
    print(f"Specific yield      : {sy:.0f} kWh/kWp/yr")
    for kwp in config.PV_SIZES_KWP:
        print(f"  {kwp:2d} kWp array -> {annual_yield(kwp, solar=solar):,.0f} kWh/yr")
