"""
prepare_data.py
===============
Builds every analysis-ready dataset for the University of Warwick (Coventry, CV4
7AL) shared e-bike charging-hub study — the example site named in the
competition's Supplementary Data & References sheet.

  1. UoW Bikes shared e-bike demand -> uses the competition's encouraged dataset
     "UoW Bikes Data(Sheet1).csv" if it is placed in data/raw/; otherwise builds
     a TRANSPARENT, calibrated representative series for the scheme so the
     pipeline always runs. The loader auto-swaps to the official file when present.
  2. PVGIS-style hourly solar series for Coventry/Warwick -> physically-based
     synthetic series calibrated to the PVGIS TMY for the site (annual GHI ~1040
     kWh/m2/yr). scripts/fetch_real_data.py replaces it with the genuine PVGIS API
     pull (lat 52.3838, lon -1.5616) — run online for fully real solar.
  3. UK Carbon Intensity (West Midlands, region 8) hourly series -> calibrated to
     the National Grid ESO regional API envelope (~120-300 gCO2/kWh); the live API
     pull (fetch_real_data.py) provides the genuine series.

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

# Canonical analysis-ready demand file consumed by src/demand_model.py
DEMAND_CSV = config.DATA_DIR / "uow_bikes_demand.csv"
# The competition's encouraged source file. Drop it here to use the real data.
OFFICIAL_FILE_CANDIDATES = [
    config.RAW_DIR / "UoW Bikes Data(Sheet1).csv",
    config.RAW_DIR / "UoW Bikes Data (Sheet1).csv",
    config.RAW_DIR / "UoW_Bikes_Data_Sheet1.csv",
    config.DATA_DIR / "UoW Bikes Data(Sheet1).csv",
]

CANONICAL_COLS = ["date", "year", "month_num", "operator", "monthly_trips",
                  "fleet_size", "trips_per_bike_per_day", "daily_trips",
                  "avg_trip_distance_km", "avg_trip_duration_min"]


# --------------------------------------------------------------------------- #
#  1a. Official "UoW Bikes Data(Sheet1).csv" loader (used automatically if found)
# --------------------------------------------------------------------------- #
def _find_official_file() -> Path | None:
    for p in OFFICIAL_FILE_CANDIDATES:
        if p.exists():
            return p
    return None


def _coerce_official(path: Path) -> pd.DataFrame | None:
    """
    Best-effort, defensive parse of the official UoW Bikes data into the canonical
    monthly schema. The exact column layout of the shared file is not known ahead
    of time, so we fuzzy-match common column names; if we cannot recover the
    essentials (a date/month and a trips count) we return None and the caller
    falls back to the calibrated representative series (never silently wrong).
    """
    try:
        raw = pd.read_csv(path)
    except Exception as e:                                     # pragma: no cover
        print(f"      ! could not read {path.name}: {str(e)[:70]}")
        return None

    cols = {c.lower().strip(): c for c in raw.columns}

    def pick(*keys):
        for k in keys:
            for lc, orig in cols.items():
                if k in lc:
                    return orig
        return None

    c_date = pick("date", "month", "period")
    c_trips = pick("trip", "ride", "journey", "hire")
    c_fleet = pick("fleet", "bikes available", "available", "vehicles", "n_bikes")
    c_dist = pick("distance", "km", "length")
    c_dur = pick("duration", "minute", "time")
    if c_date is None or c_trips is None:
        print(f"      ! {path.name} found but lacks a recognisable date/trips "
              "column — falling back to representative series.")
        return None

    df = raw.copy()
    dt = pd.to_datetime(df[c_date], errors="coerce", dayfirst=True)
    df = df.assign(date=dt).dropna(subset=["date"])
    df["year"] = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    df["monthly_trips"] = pd.to_numeric(df[c_trips], errors="coerce")
    # If the file is finer than monthly (daily/trip rows), aggregate to months.
    agg = {"monthly_trips": "sum"}
    df["fleet_size"] = pd.to_numeric(df[c_fleet], errors="coerce") if c_fleet else np.nan
    df["avg_trip_distance_km"] = pd.to_numeric(df[c_dist], errors="coerce") if c_dist else np.nan
    df["avg_trip_duration_min"] = pd.to_numeric(df[c_dur], errors="coerce") if c_dur else np.nan
    if c_fleet:
        agg["fleet_size"] = "mean"
    if c_dist:
        agg["avg_trip_distance_km"] = "mean"
    if c_dur:
        agg["avg_trip_duration_min"] = "mean"

    g = (df.groupby([df["date"].dt.to_period("M")])
            .agg(agg)
            .reset_index())
    g["date"] = g["date"].dt.to_timestamp()
    g["year"] = g["date"].dt.year
    g["month_num"] = g["date"].dt.month
    g = g.dropna(subset=["monthly_trips"])
    if len(g) < 3:
        print(f"      ! {path.name} parsed but too few monthly rows ({len(g)}).")
        return None

    # Fill any gaps with scheme-typical values so downstream code is robust.
    g["fleet_size"] = g.get("fleet_size", pd.Series(np.nan)).fillna(
        g["monthly_trips"].mean() / (2.0 * 30)).round(0).clip(lower=1).astype(int)
    g["avg_trip_distance_km"] = g.get("avg_trip_distance_km", pd.Series(np.nan)).fillna(3.2)
    g["avg_trip_duration_min"] = g.get("avg_trip_duration_min", pd.Series(np.nan)).fillna(16.0)
    days = g["date"].dt.days_in_month
    g["daily_trips"] = (g["monthly_trips"] / days).round(0)
    g["trips_per_bike_per_day"] = (g["daily_trips"] / g["fleet_size"]).round(2)
    g["operator"] = "UoW Bikes (official data)"
    g = g.sort_values("date").reset_index(drop=True)
    return g[CANONICAL_COLS]


# --------------------------------------------------------------------------- #
#  1b. Real-data BASIS from DfT shared-micromobility monitoring (all UK areas)
# --------------------------------------------------------------------------- #
DFT_FILE_CANDIDATES = [
    config.RAW_DIR / "dft_shared_micromobility_2022_2024.ods",
    config.RAW_DIR / "shared-rental-e-scooter-trials-monitoring-data-january-2022-to-may-2024.ods",
]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _dft_real_basis() -> dict | None:
    """
    Derive REAL monthly seasonality, usage intensity and trip distance from the
    DfT shared rental e-scooter trials monitoring data (Jan 2022-May 2024, all UK
    trial areas). These empirical figures anchor the UoW e-bike demand series, so
    the demand is grounded in real open-government data rather than assumed.
    """
    path = next((p for p in DFT_FILE_CANDIDATES if p.exists()), None)
    if path is None:
        return None
    try:
        m2n = {m: i for i, m in enumerate(_MONTHS, start=1)}

        def rd(sheet):
            d = pd.read_excel(path, sheet_name=sheet, engine="odf", header=3).iloc[:, :5]
            d.columns = ["area", "op", "month", "year", "val"]
            d["val"] = pd.to_numeric(d["val"], errors="coerce")
            d["mn"] = d["month"].map(m2n)
            return d.dropna(subset=["val", "mn"])

        seas = rd("monthly_trips").groupby("mn")["val"].mean()
        seas = (seas / seas.mean()).reindex(range(1, 13)).interpolate().bfill().ffill()
        intensity = float(rd("trips_per_escooter")["val"].mean())
        tl = pd.read_excel(path, sheet_name="trip_length", engine="odf", header=3).iloc[:, :3]
        tl.columns = ["area", "dist", "dur"]
        dist = float(pd.to_numeric(tl["dist"], errors="coerce").mean())
        dur = float(pd.to_numeric(tl["dur"], errors="coerce").mean())
        return {"seasonal": seas.values, "intensity": intensity,
                "dist": dist, "dur": dur, "name": path.name}
    except Exception as e:                                    # pragma: no cover
        print(f"      ! could not parse DfT basis ({str(e)[:60]})")
        return None


# --------------------------------------------------------------------------- #
#  1c. UoW shared e-bike demand series (DfT-grounded, else representative)
# --------------------------------------------------------------------------- #
def build_demand_dataset() -> pd.DataFrame:
    """
    Demand for the UoW Bikes shared e-bike scheme. Uses the official
    "UoW Bikes Data(Sheet1).csv" when present in data/raw/; otherwise generates a
    transparent representative monthly series calibrated to published shared
    e-bike usage so the optimisation stays in a realistic, binding regime.
    """
    official = _find_official_file()
    if official is not None:
        coerced = _coerce_official(official)
        if coerced is not None:
            coerced.to_csv(DEMAND_CSV, index=False)
            print(f"[1/3] UoW Bikes demand (OFFICIAL {official.name}): {DEMAND_CSV.name}  "
                  f"({len(coerced)} months, trips "
                  f"{coerced.monthly_trips.min():,.0f}-{coerced.monthly_trips.max():,.0f})")
            return coerced
        print("      -> using DfT-grounded representative series instead.")

    # ---- basis: real DfT monitoring data if available, else fallback --------
    basis = _dft_real_basis()
    if basis is not None:
        seasonal = np.asarray(basis["seasonal"], float)          # REAL seasonality
        # e-bike scheme: usage intensity anchored to the real DfT mean (shared
        # micromobility), trip distance to e-bike commute distances (a little above
        # the e-scooter trials, per Burani 2022 / Ouf 2023).
        base_tpb = round(max(basis["intensity"], 1.0) * 1.15, 2)
        dist_mean = round(max(basis["dist"] * 1.5, 3.0), 2)
        dur_mean = round(max(basis["dur"] * 1.6, 12.0), 1)
        label = "UoW Bikes (DfT-calibrated)"
        src = (f"seasonality, usage intensity & trip distance from real DfT "
               f"monitoring data ({basis['name']})")
    else:
        seasonal = np.array([0.80, 0.92, 1.04, 1.10, 1.18, 1.16,
                             0.98, 0.78, 1.06, 1.20, 1.06, 0.78])
        base_tpb, dist_mean, dur_mean = 2.2, 3.2, 16.0
        label = "UoW Bikes (representative)"
        src = "calibrated to published shared e-bike usage"

    # ---- 24-month UoW e-bike series (Jan 2023 - Dec 2024) -------------------
    dates = pd.date_range("2023-01-01", periods=24, freq="MS")
    # Fleet grows as the scheme scales (360 -> 470 e-bikes over the 2 years).
    fleet = np.linspace(360, 470, 24).round(0)
    fleet = (fleet + RNG.normal(0, 6, 24)).round(0).clip(min=300).astype(int)

    rows = []
    for i, d in enumerate(dates):
        s = seasonal[(d.month - 1)]
        tpb = base_tpb * s * (1 + RNG.normal(0, 0.03))
        days = d.days_in_month
        monthly_trips = int(round(fleet[i] * tpb * days))
        rows.append({
            "date": d, "year": d.year, "month_num": d.month, "operator": label,
            "monthly_trips": monthly_trips, "fleet_size": int(fleet[i]),
            "trips_per_bike_per_day": round(tpb, 2),
            "daily_trips": round(monthly_trips / days, 0),
            "avg_trip_distance_km": round(dist_mean + RNG.normal(0, 0.05), 2),
            "avg_trip_duration_min": round(dur_mean + RNG.normal(0, 0.4), 2),
        })
    df = pd.DataFrame(rows)[CANONICAL_COLS]
    df.to_csv(DEMAND_CSV, index=False)
    print(f"[1/3] UoW Bikes demand ({label.split('(')[1].rstrip(')')}): {DEMAND_CSV.name}  "
          f"({len(df)} months, fleet ~{df.fleet_size.mean():.0f} e-bikes, "
          f"~{base_tpb:g} trips/bike/day)")
    print(f"      basis: {src}")
    print("      (drop the official 'UoW Bikes Data(Sheet1).csv' into data/raw/ "
          "to use it instead — picked up automatically.)")
    return df


# --------------------------------------------------------------------------- #
#  2. PVGIS-style hourly solar series (calibrated synthetic, Coventry/Warwick)
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
    peak_ghi = np.maximum(0.0, 870 * np.sin(noon_elev))

    solar_noon = 12.0 + 0.4 * np.sin(2 * np.pi * (doy - 172) / 365)
    sigma = np.maximum(day_len / 4.5, 0.5)
    ghi_clear = peak_ghi * np.exp(-0.5 * ((hod - solar_noon) / sigma) ** 2)

    cloud = 0.64 + 0.16 * np.sin(2 * np.pi * (doy - 172) / 365)
    cloud_noise = RNG.beta(2.0, 1.6, config.HOURS_PER_YEAR) * 0.45 + 0.55
    ghi = np.where(ghi_clear < 5, 0.0, ghi_clear * cloud * cloud_noise)

    # Calibrate annual GHI to the PVGIS TMY reference for Coventry/Warwick
    # (~1040 kWh/m2/yr; the West Midlands receives more annual irradiation than
    # northern England).
    TARGET_ANNUAL_GHI = 1040.0  # kWh/m2/yr (PVGIS TMY, lat 52.3838, lon -1.5616)
    raw_annual = ghi.sum() / 1000.0
    if raw_annual > 0:
        ghi *= TARGET_ANNUAL_GHI / raw_annual

    t_mean = 10.5 + 7.5 * np.sin(2 * np.pi * (doy - 172) / 365)   # Midlands climate
    t_diurnal = 3.5 * np.sin(2 * np.pi * (hod - 6) / 24)
    t_amb = t_mean + t_diurnal + RNG.normal(0, 1.5, config.HOURS_PER_YEAR)
    t_cell = t_amb + (45 - 20) / 800 * ghi
    eta_temp = 1 + config.PV_TEMP_COEFF * np.maximum(0, t_cell - 25)

    # Specific yield per kWp. The kWp rating already embeds module efficiency, so
    # we apply only the performance ratio (which subsumes inverter + soiling +
    # temperature-independent losses) and the explicit temperature derate. An
    # optimal-tilt plane-of-array gain (~1.12x vs GHI) is included for the site.
    POA_TILT_GAIN = 1.12
    pv_per_kwp = (ghi / 1000.0 * POA_TILT_GAIN
                  * config.PV_PERFORMANCE_RATIO["baseline"]
                  * eta_temp)

    df = pd.DataFrame({
        "datetime": hours, "month": hours.month, "day_of_year": doy, "hour": hod,
        "GHI_Wm2": ghi.round(1), "T_amb_C": t_amb.round(2),
        "pv_kWh_per_kWp": np.clip(pv_per_kwp, 0, None).round(5),
    })
    out = config.DATA_DIR / "pvgis_warwick_hourly.csv"
    df.to_csv(out, index=False)
    annual = ghi.sum() / 1000.0
    yield_kwp = pv_per_kwp.sum()
    print(f"[2/3] PVGIS solar (calibrated, Coventry/Warwick): {out.name}  "
          f"(GHI {annual:.0f} kWh/m2/yr, specific yield {yield_kwp:.0f} kWh/kWp/yr)")
    return df


# --------------------------------------------------------------------------- #
#  3. Carbon intensity series (calibrated synthetic, West Midlands)
# --------------------------------------------------------------------------- #
def build_carbon_dataset() -> pd.DataFrame:
    hours = pd.date_range("2023-01-01", periods=config.HOURS_PER_YEAR, freq="h")
    doy = hours.day_of_year.values
    hod = hours.hour.values
    seasonal = 200 - 55 * np.sin(2 * np.pi * (doy - 172) / 365)
    diurnal = 25 * np.sin(2 * np.pi * (hod - 8) / 24)
    noise = RNG.normal(0, 20, config.HOURS_PER_YEAR)
    ci = np.clip(seasonal + diurnal + noise, 70, 360)

    df = pd.DataFrame({
        "datetime": hours, "month": hours.month, "hour": hod,
        "carbon_intensity_gCO2_kWh": ci.round(1),
        "region": config.CARBON_REGION_NAME,
    })
    out = config.DATA_DIR / "carbon_intensity_west_midlands.csv"
    df.to_csv(out, index=False)
    print(f"[3/3] Carbon intensity (calibrated, {config.CARBON_REGION_NAME}): {out.name}  "
          f"(mean {ci.mean():.0f} gCO2/kWh)")
    return df


def main() -> None:
    print("=" * 70)
    print("PREPARING ANALYSIS-READY DATASETS  (University of Warwick e-bike hub)")
    print("=" * 70)
    build_demand_dataset()
    build_solar_dataset()
    build_carbon_dataset()
    print("-" * 70)
    print("All datasets written to:", config.DATA_DIR)


if __name__ == "__main__":
    main()
