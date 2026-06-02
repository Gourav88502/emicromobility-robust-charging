"""
prepare_data.py
===============
Builds every analysis-ready dataset listed in the approved Data Inventory.

  1. DfT Newcastle / Neuron e-scooter data  -> REAL data extracted from the
     official DfT monitoring spreadsheet (.ods) shipped in data/raw/.
  2. PVGIS-style hourly solar series for Newcastle -> physically-based synthetic
     series calibrated to PVGIS TMY (annual GHI ~900 kWh/m2/yr). A live-fetch
     helper (scripts/fetch_real_data.py) can replace it with the genuine API pull.
  3. UK Carbon Intensity (North East England) hourly series -> calibrated to the
     National Grid ESO regional API envelope (~100-350 gCO2/kWh).

Run:
    python scripts/prepare_data.py
Outputs land in data/ as tidy CSVs consumed by the rest of the pipeline.
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config

RNG = np.random.default_rng(config.RANDOM_SEED)

MONTH_TO_NUM = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}


# --------------------------------------------------------------------------- #
#  1. Real DfT Newcastle / Neuron data
# --------------------------------------------------------------------------- #
def _read_dft_sheet(ods_path: Path, sheet: str, value_name: str) -> pd.DataFrame:
    df = pd.read_excel(ods_path, sheet_name=sheet, engine="odf", header=3)
    df = df.iloc[:, :5]
    df.columns = ["area", "operator", "month", "year", value_name]
    df = df[df["area"] == "Newcastle City Council"].copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df[value_name] = pd.to_numeric(df[value_name], errors="coerce")
    df["month_num"] = df["month"].map(MONTH_TO_NUM)
    return df.dropna(subset=["month_num", "year"])


def build_dft_dataset() -> pd.DataFrame:
    ods = config.RAW_DIR / "dft_escooter_trials_jan2022_may2024.ods"
    if not ods.exists():
        raise FileNotFoundError(
            f"Real DfT spreadsheet not found at {ods}. "
            "Place the official .ods there or run fetch_real_data.py."
        )

    trips = _read_dft_sheet(ods, "monthly_trips", "monthly_trips")
    avail = _read_dft_sheet(ods, "daily_availability", "fleet_size")
    tpe = _read_dft_sheet(ods, "trips_per_escooter", "trips_per_scooter_per_day")

    key = ["month_num", "year"]
    df = (trips.merge(avail[key + ["fleet_size"]], on=key, how="inner")
               .merge(tpe[key + ["trips_per_scooter_per_day"]], on=key, how="inner"))

    # Trip length sheet reports a single Newcastle average (dist, duration).
    tl = pd.read_excel(ods, sheet_name="trip_length", engine="odf", header=3).iloc[:, :3]
    tl.columns = ["area", "dist", "dur"]
    nc = tl[tl["area"] == "Newcastle City Council"]
    avg_dist = float(nc["dist"].iloc[0]) if len(nc) else 1.64
    avg_dur = float(nc["dur"].iloc[0]) if len(nc) else 8.52

    df["avg_trip_distance_km"] = round(avg_dist, 2)
    df["avg_trip_duration_min"] = round(avg_dur, 2)
    df["date"] = pd.to_datetime(dict(year=df["year"].astype(int),
                                     month=df["month_num"].astype(int), day=1))
    df = df.sort_values("date").reset_index(drop=True)
    df["fleet_size"] = df["fleet_size"].round(0).astype(int)
    df["daily_trips"] = (df["monthly_trips"] / df["date"].dt.days_in_month).round(0)

    out_cols = ["date", "year", "month_num", "operator", "monthly_trips",
                "fleet_size", "trips_per_scooter_per_day", "daily_trips",
                "avg_trip_distance_km", "avg_trip_duration_min"]
    df = df[out_cols]
    out = config.DATA_DIR / "dft_newcastle_scooter_data.csv"
    df.to_csv(out, index=False)
    print(f"[1/3] DfT Newcastle/Neuron (REAL): {out.name}  "
          f"({len(df)} months, trips {df.monthly_trips.min():,}-{df.monthly_trips.max():,})")
    return df


# --------------------------------------------------------------------------- #
#  2. PVGIS-style hourly solar series (calibrated synthetic)
# --------------------------------------------------------------------------- #
def build_solar_dataset() -> pd.DataFrame:
    hours = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
    doy = hours.day_of_year.values
    hod = hours.hour.values

    lat = np.radians(config.SITE_LAT)
    decl = np.radians(23.45 * np.sin(np.radians(360 / 365 * (doy - 81))))
    cos_hss = np.clip(-np.tan(lat) * np.tan(decl), -1, 1)
    day_len = 2 * np.degrees(np.arccos(cos_hss)) / 15.0
    noon_elev = np.pi / 2 - lat + decl
    peak_ghi = np.maximum(0.0, 820 * np.sin(noon_elev))

    solar_noon = 12.0 + 0.4 * np.sin(2 * np.pi * (doy - 172) / 365)
    sigma = np.maximum(day_len / 4.5, 0.5)
    ghi_clear = peak_ghi * np.exp(-0.5 * ((hod - solar_noon) / sigma) ** 2)

    cloud = 0.62 + 0.16 * np.sin(2 * np.pi * (doy - 172) / 365)
    cloud_noise = RNG.beta(2.0, 1.6, config.HOURS_PER_YEAR) * 0.45 + 0.55
    ghi = np.where(ghi_clear < 5, 0.0, ghi_clear * cloud * cloud_noise)

    # Calibrate annual GHI to the PVGIS TMY reference for Newcastle (~900 kWh/m2/yr).
    TARGET_ANNUAL_GHI = 900.0  # kWh/m2/yr (PVGIS TMY, lat 54.978, lon -1.618)
    raw_annual = ghi.sum() / 1000.0
    if raw_annual > 0:
        ghi *= TARGET_ANNUAL_GHI / raw_annual

    t_mean = 9.0 + 7.0 * np.sin(2 * np.pi * (doy - 172) / 365)
    t_diurnal = 3.5 * np.sin(2 * np.pi * (hod - 6) / 24)
    t_amb = t_mean + t_diurnal + RNG.normal(0, 1.5, config.HOURS_PER_YEAR)
    t_cell = t_amb + (45 - 20) / 800 * ghi
    eta_temp = 1 + config.PV_TEMP_COEFF * np.maximum(0, t_cell - 25)

    # Specific yield per kWp. The kWp rating already embeds module efficiency, so
    # we apply only the performance ratio (which subsumes inverter + soiling +
    # temperature-independent losses) and the explicit temperature derate. An
    # optimal-tilt plane-of-array gain (~1.12x vs GHI) is included for Newcastle.
    POA_TILT_GAIN = 1.12
    pv_per_kwp = (ghi / 1000.0 * POA_TILT_GAIN
                  * config.PV_PERFORMANCE_RATIO["baseline"]
                  * eta_temp)

    df = pd.DataFrame({
        "datetime": hours, "month": hours.month, "day_of_year": doy, "hour": hod,
        "GHI_Wm2": ghi.round(1), "T_amb_C": t_amb.round(2),
        "pv_kWh_per_kWp": np.clip(pv_per_kwp, 0, None).round(5),
    })
    out = config.DATA_DIR / "pvgis_newcastle_hourly.csv"
    df.to_csv(out, index=False)
    annual = ghi.sum() / 1000.0
    yield_kwp = pv_per_kwp.sum()
    print(f"[2/3] PVGIS solar (calibrated): {out.name}  "
          f"(GHI {annual:.0f} kWh/m2/yr, specific yield {yield_kwp:.0f} kWh/kWp/yr)")
    return df


# --------------------------------------------------------------------------- #
#  3. Carbon intensity series (calibrated synthetic)
# --------------------------------------------------------------------------- #
def build_carbon_dataset() -> pd.DataFrame:
    hours = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
    doy = hours.day_of_year.values
    hod = hours.hour.values
    seasonal = 220 - 60 * np.sin(2 * np.pi * (doy - 172) / 365)
    diurnal = 25 * np.sin(2 * np.pi * (hod - 8) / 24)
    noise = RNG.normal(0, 20, config.HOURS_PER_YEAR)
    ci = np.clip(seasonal + diurnal + noise, 80, 380)

    df = pd.DataFrame({
        "datetime": hours, "month": hours.month, "hour": hod,
        "carbon_intensity_gCO2_kWh": ci.round(1),
        "region": config.CARBON_REGION_NAME,
    })
    out = config.DATA_DIR / "carbon_intensity_ne_england.csv"
    df.to_csv(out, index=False)
    print(f"[3/3] Carbon intensity (calibrated): {out.name}  "
          f"(mean {ci.mean():.0f} gCO2/kWh)")
    return df


def main() -> None:
    print("=" * 70)
    print("PREPARING ANALYSIS-READY DATASETS  (Newcastle e-micromobility)")
    print("=" * 70)
    build_dft_dataset()
    build_solar_dataset()
    build_carbon_dataset()
    print("-" * 70)
    print("All datasets written to:", config.DATA_DIR)


if __name__ == "__main__":
    main()
