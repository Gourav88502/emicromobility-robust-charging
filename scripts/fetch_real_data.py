"""
fetch_real_data.py  (OPTIONAL — requires internet)
===================================================
Replaces the calibrated synthetic solar / carbon series with genuine live API
pulls, so the model can run on fully real data end-to-end.

    python scripts/fetch_real_data.py

  * PVGIS (EU JRC) seriescalc API  -> hourly PV power for Newcastle
  * UK Carbon Intensity API        -> regional half-hourly carbon intensity (NE England)

If a call fails (offline / API change) the script leaves the existing calibrated
CSV in place and prints a warning, so the pipeline still runs. The real DfT
e-scooter data is always read from the bundled .ods in data/raw/.
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config


def fetch_pvgis() -> bool:
    """Hourly PV (kWh/kWp) for Newcastle from PVGIS seriescalc (TMY year)."""
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
    qp = dict(lat=config.SITE_LAT, lon=config.SITE_LON, outputformat="json",
              pvcalculation=1, peakpower=1, loss=14, optimalangles=1,
              startyear=2020, endyear=2020)
    try:
        r = requests.get(url, params=qp, timeout=60)
        r.raise_for_status()
        hourly = r.json()["outputs"]["hourly"]
        d = pd.DataFrame(hourly)
        d["datetime"] = pd.to_datetime(d["time"], format="%Y%m%d:%H%M")
        d = d.iloc[:config.HOURS_PER_YEAR].reset_index(drop=True)
        out = pd.DataFrame({
            "datetime": d["datetime"],
            "month": d["datetime"].dt.month,
            "day_of_year": d["datetime"].dt.dayofyear,
            "hour": d["datetime"].dt.hour,
            "GHI_Wm2": d.get("G(i)", pd.Series(np.zeros(len(d)))).round(1),
            "T_amb_C": d.get("T2m", pd.Series(np.full(len(d), 9.0))).round(2),
            "pv_kWh_per_kWp": (d["P"] / 1000.0).round(5),   # P is W per kWp
        })
        out.to_csv(config.DATA_DIR / "pvgis_newcastle_hourly.csv", index=False)
        print(f"  PVGIS OK: specific yield {out['pv_kWh_per_kWp'].sum():.0f} kWh/kWp/yr")
        return True
    except Exception as e:
        print(f"  PVGIS fetch failed ({e}); keeping calibrated series.")
        return False


def fetch_carbon() -> bool:
    """A representative week of NE-England carbon intensity, tiled to a year."""
    url = ("https://api.carbonintensity.org.uk/regional/intensity/"
           "2023-07-01T00:00Z/2023-07-08T00:00Z/regionid/"
           f"{config.CARBON_REGION_ID}")
    try:
        r = requests.get(url, timeout=60, headers={"Accept": "application/json"})
        r.raise_for_status()
        data = r.json()["data"]["data"]
        vals = [d["intensity"]["forecast"] for d in data if d["intensity"]["forecast"]]
        if not vals:
            raise ValueError("no intensity values returned")
        hourly = np.array(vals[::2])[:168]                  # half-hourly -> hourly, 1 week
        tiled = np.resize(hourly, config.HOURS_PER_YEAR)
        hours = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
        out = pd.DataFrame({
            "datetime": hours, "month": hours.month, "hour": hours.hour,
            "carbon_intensity_gCO2_kWh": np.round(tiled, 1),
            "region": config.CARBON_REGION_NAME})
        out.to_csv(config.DATA_DIR / "carbon_intensity_ne_england.csv", index=False)
        print(f"  Carbon API OK: mean {tiled.mean():.0f} gCO2/kWh")
        return True
    except Exception as e:
        print(f"  Carbon API fetch failed ({e}); keeping calibrated series.")
        return False


def main():
    print("Fetching live data (PVGIS + UK Carbon Intensity) ...")
    fetch_pvgis()
    fetch_carbon()
    print("Done. (Real DfT e-scooter data is read from data/raw/ by prepare_data.py.)")


if __name__ == "__main__":
    main()
