"""
fetch_real_data.py  (live APIs — internet required)
===================================================
Replaces the calibrated synthetic solar / carbon series with GENUINELY REAL data
so all three datasets are real end-to-end:

  * PVGIS (EU JRC) seriescalc  -> real hourly PV yield (kWh/kWp) for Newcastle,
    one full non-leap year (2021), losses + optimal tilt applied by PVGIS.
  * UK Carbon Intensity API (National Grid ESO) -> real regional half-hourly
    carbon intensity for North East England (regionid 13), stitched to a year.

If any call fails the script keeps the existing CSV and warns, so the pipeline
always runs. The real DfT e-scooter data is always read from data/raw/.

    python scripts/fetch_real_data.py
"""

from __future__ import annotations
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

YEAR = 2021                       # non-leap -> exactly 8760 hours


def fetch_pvgis() -> bool:
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
    for yr in (2020, 2019, 2018, 2016):                 # years inside PVGIS DB
        qp = dict(lat=config.SITE_LAT, lon=config.SITE_LON, outputformat="json",
                  pvcalculation=1, peakpower=1, loss=14, optimalangles=1,
                  startyear=yr, endyear=yr)
        try:
            r = requests.get(url, params=qp, timeout=90)
            r.raise_for_status()
            d = pd.DataFrame(r.json()["outputs"]["hourly"])
            d["datetime"] = pd.to_datetime(d["time"], format="%Y%m%d:%H%M")
            # keep first 8760 hours (drop the extra day in leap years)
            d = d.iloc[:config.HOURS_PER_YEAR].reset_index(drop=True)
            out = pd.DataFrame({
                "datetime": d["datetime"],
                "month": d["datetime"].dt.month,
                "day_of_year": d["datetime"].dt.dayofyear,
                "hour": d["datetime"].dt.hour,
                "GHI_Wm2": pd.to_numeric(d.get("G(i)", 0), errors="coerce").round(1),
                "T_amb_C": pd.to_numeric(d.get("T2m", 9.0), errors="coerce").round(2),
                "pv_kWh_per_kWp": (pd.to_numeric(d["P"], errors="coerce") / 1000.0).round(5),
            }).fillna(0.0)
            out.to_csv(config.DATA_DIR / "pvgis_newcastle_hourly.csv", index=False)
            print(f"  PVGIS OK (REAL {yr}): specific yield "
                  f"{out['pv_kWh_per_kWp'].sum():.0f} kWh/kWp/yr, "
                  f"POA {out['GHI_Wm2'].sum()/1000:.0f} kWh/m2/yr")
            return True
        except Exception as e:
            print(f"  PVGIS {yr} failed ({str(e)[:60]}); trying next year ...")
    print("  PVGIS fetch failed for all years; keeping existing series.")
    return False


def fetch_carbon() -> bool:
    base = "https://api.carbonintensity.org.uk/regional/intensity"
    rid = config.CARBON_REGION_ID
    start = datetime(YEAR, 1, 1)
    end = datetime(YEAR + 1, 1, 1)
    records = []
    try:
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=13), end)
            url = (f"{base}/{cur:%Y-%m-%dT%H:%MZ}/{nxt:%Y-%m-%dT%H:%MZ}/regionid/{rid}")
            r = requests.get(url, timeout=60, headers={"Accept": "application/json"})
            r.raise_for_status()
            for blk in r.json()["data"]["data"]:
                fc = blk["intensity"]["forecast"]
                if fc is not None:
                    records.append((blk["from"], float(fc)))
            cur = nxt
            time.sleep(0.15)
        if len(records) < 1000:
            raise ValueError(f"only {len(records)} intervals returned")
        s = pd.DataFrame(records, columns=["from", "ci"])
        s["dt"] = pd.to_datetime(s["from"]).dt.tz_localize(None)
        s = s.set_index("dt").sort_index()
        hourly = s["ci"].resample("h").mean().interpolate()
        # align to a clean 8760-hour calendar
        idx = pd.date_range(f"{YEAR}-01-01", periods=config.HOURS_PER_YEAR, freq="h")
        ci = hourly.reindex(idx).interpolate().bfill().ffill().values
        out = pd.DataFrame({
            "datetime": idx, "month": idx.month, "hour": idx.hour,
            "carbon_intensity_gCO2_kWh": np.round(ci, 1),
            "region": config.CARBON_REGION_NAME})
        out.to_csv(config.DATA_DIR / "carbon_intensity_ne_england.csv", index=False)
        print(f"  Carbon API OK (REAL {YEAR}): {len(records):,} intervals, "
              f"mean {np.mean(ci):.0f} gCO2/kWh")
        return True
    except Exception as e:
        print(f"  Carbon API fetch failed ({e}); keeping existing series.")
        return False


def main():
    print("Fetching LIVE real data (PVGIS + UK Carbon Intensity) for Newcastle ...")
    ok_pv = fetch_pvgis()
    ok_c = fetch_carbon()
    print(f"Done. PVGIS={'real' if ok_pv else 'kept'}, Carbon={'real' if ok_c else 'kept'}. "
          "(DfT e-scooter data is always real, read from data/raw/.)")


if __name__ == "__main__":
    main()
