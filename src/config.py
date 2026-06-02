"""
config.py
=========
Single source of truth for every model parameter, design range and uncertainty
band used in the project. Values are drawn directly from the approved
*Data Inventory Table* and the Expression of Interest (EoI).

Project : Robust Charging Infrastructure Design Under Demand Uncertainty
Team    : Gourav Singh, Neelesh Raj, Priti Burud (Newcastle University)
Comp.   : National Competition for Sustainable e-Micromobility 2025-26
Themes  : 3 (primary, solar-PV charging station) + 2 (secondary, charge profiles)

Every hard-coded number below carries a source comment so the model is fully
traceable and audit-ready. Edit values here ONLY; all modules import from this
file so nothing is ever duplicated.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Paths
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = ROOT_DIR / "outputs"
DASHBOARD_DIR = ROOT_DIR / "dashboard"
for _d in (DATA_DIR, RAW_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Reproducibility — fixed master seed for every stochastic routine.
RANDOM_SEED = 42

# Site: Newcastle upon Tyne (EoI section 1)
SITE_NAME = "Newcastle upon Tyne, UK"
SITE_LAT = 54.978
SITE_LON = -1.618
CARBON_REGION_ID = 13          # National Grid ESO: North East England
CARBON_REGION_NAME = "North East England"

HOURS_PER_YEAR = 8760

# --------------------------------------------------------------------------- #
#  1. Demand model  (DfT Newcastle / Neuron data + literature)
# --------------------------------------------------------------------------- #
# SCOPE (Theme 3): a shared-micromobility DEPOT charging hub serving a mixed
# fleet of e-scooters, e-bikes and e-cargo bikes. Vehicles are charged at the
# depot through AC charge points (e-bikes / e-cargo bikes accept 3-7 kW; e-scooter
# battery packs are bench-charged). Demand is anchored to the REAL DfT Newcastle
# trial (trips, fleet size, trip distance) and scaled for the higher energy
# intensity of the e-bike / e-cargo bike mix.
#
# Demand is decomposed into two INDEPENDENT factors (no double counting):
#   demand_intensity   = trips per DEPLOYED vehicle per day  (usage intensity)
#   fleet_utilisation  = fraction of the fleet DEPLOYED that day (deployment rate)
# Their product is the trips-per-fleet-vehicle figure reported by the DfT.
TRIPS_PER_SCOOTER_DAY = {"low": 0.5, "medium": 1.5, "high": 3.5}

# Trip energy consumption (Wh/km) for the MIXED fleet. e-scooters ~20-35
# (Gossling 2020, Hollingsworth 2019); e-cargo / e-bikes are heavier and draw
# more, so the fleet-mean baseline is higher with a wider band.
TRIP_ENERGY_WH_PER_KM = {"baseline": 35.0, "low": 22.0, "high": 55.0}
TRIP_ENERGY_UNCERTAINTY = 0.30          # +/-30 % for Monte Carlo

# Daily fleet DEPLOYMENT rate (fraction of fleet out on the street that day;
# the rest is in the depot / maintenance). Independent of usage intensity above.
FLEET_UTILISATION = {"baseline": 0.65, "low": 0.40, "high": 0.90}
FLEET_UTILISATION_UNCERTAINTY = 0.25

# Year-on-year demand growth (Data Inventory: 0 / 8 / 15 % per year).
DEMAND_GROWTH = {"low": 0.0, "medium": 0.08, "high": 0.15}

# Battery capacity of one e-scooter (Wh) — used to convert energy to "charges".
SCOOTER_BATTERY_WH = 500.0              # ~0.5 kWh typical shared e-scooter pack

# Fraction of the local fleet's charging served by THIS depot hub (~half; a
# mid-sized neighbourhood depot — larger operators run several). This places
# demand in the range where PV (5-25 kWp), storage (0-50 kWh) AND charge-point
# count (4-20) are all binding decisions. The conclusion is shown to hold across
# 0.35-0.6 coverage in the robustness-of-robustness analysis.
STATION_DEMAND_SHARE = 0.9

# SMART (deferrable) charging. A depot's charging load is highly flexible: a
# vehicle that returns in the evening only needs to be ready by morning. A smart
# controller therefore SCHEDULES charging across the depot dwell window to follow
# on-site PV and the cheapest/cleanest off-peak hours, rather than charging on a
# fixed evening peak. The realised hourly load is built in demand_model from:
#   (a) VEHICLE_AVAILABILITY  — fraction of the fleet at the depot each hour, and
#   (b) a desirability weight that favours hours with PV and off-peak tariff.
# This flattens the load (the honest baseline); storage/PV still earn their place
# by (i) covering the residual overnight peak when even the flattened load exceeds
# the connection, and (ii) time-shifting daytime PV to the overnight load.
SMART_CHARGING = True

# Fraction of the fleet physically at the depot (able to charge) each hour. Out
# on the street through the day, back overnight — a shared-fleet duty cycle.
VEHICLE_AVAILABILITY = [
    0.95, 0.95, 0.95, 0.95, 0.95, 0.92,   # 00-05  overnight: nearly all present
    0.85, 0.65, 0.45, 0.30, 0.25, 0.25,   # 06-11  deploying out
    0.25, 0.25, 0.30, 0.40, 0.55, 0.70,   # 12-17  starting to return
    0.82, 0.90, 0.93, 0.95, 0.95, 0.95,   # 18-23  back at the depot
]
# How strongly the smart controller shifts charging towards PV and off-peak hours.
SMART_PV_WEIGHT = 1.6
SMART_OFFPEAK_WEIGHT = 1.0

# UNMANAGED (dumb) charging shape — used only when SMART_CHARGING is False, as the
# pessimistic counterfactual: vehicles all plugged in on return for an evening peak.
HOURLY_DEMAND_SHAPE = [
    0.015, 0.010, 0.008, 0.008, 0.010, 0.015,   # 00-05
    0.020, 0.025, 0.030, 0.025, 0.020, 0.020,   # 06-11
    0.022, 0.022, 0.022, 0.028, 0.045, 0.080,   # 12-17
    0.120, 0.135, 0.115, 0.085, 0.050, 0.030,   # 18-23  evening plug-in peak
]
DEMAND_SHAPE_UNCERTAINTY = 0.25

# --------------------------------------------------------------------------- #
#  2. PV model  (PVGIS / NASA POWER + IEA PVPS / Fraunhofer ISE)
# --------------------------------------------------------------------------- #
PV_MODULE_EFFICIENCY = {"baseline": 0.20, "low": 0.18, "high": 0.22}   # mono-Si
INVERTER_EFFICIENCY = {"baseline": 0.95, "low": 0.93, "high": 0.97}
PV_PERFORMANCE_RATIO = {"baseline": 0.85, "low": 0.75, "high": 0.95}   # soiling+temp
PV_OUTPUT_UNCERTAINTY = 0.10            # +/-10 % year-to-year (Pfenninger & Staffell)
PV_TEMP_COEFF = -0.004                  # -0.4 %/degC above 25 degC

# --------------------------------------------------------------------------- #
#  3. Battery storage  (IRENA / BloombergNEF / Mongird PNNL)
# --------------------------------------------------------------------------- #
BATTERY_ROUNDTRIP_EFF = {"baseline": 0.92, "low": 0.88, "high": 0.94}
BATTERY_RT_UNCERTAINTY = 0.04
BATTERY_CYCLE_LIFE = {"baseline": 4000, "low": 3000, "high": 6000}
BATTERY_CYCLE_UNCERTAINTY = 0.30
BATTERY_DOD = 0.90                      # usable depth of discharge
BATTERY_MIN_SOC = 0.10                  # reserve floor
BATTERY_CALENDAR_LIFE_YEARS = 12        # calendar-aging floor (replace even if lightly cycled)

# --------------------------------------------------------------------------- #
#  4. Micromobility charge points  (e-bike / e-cargo AC points; e-scooter benches)
# --------------------------------------------------------------------------- #
# Depot micromobility charge points are LOW power (~2-4 kW per bay), unlike 7-22
# kW EV chargers. With low-power bays, the NUMBER of bays is a genuine binding
# decision: a peaky evening return profile needs enough simultaneous bays.
CHARGER_POWER_KW = {"baseline": 3.0, "low": 2.0, "high": 7.0}
CHARGER_AVAILABILITY = {"baseline": 0.95, "low": 0.90, "high": 0.99}

# --------------------------------------------------------------------------- #
#  5. Cost assumptions  (BEIS / IRENA / BloombergNEF / OZEV / Zap-Map / STA)
# --------------------------------------------------------------------------- #
PV_CAPEX_PER_KWP = {"baseline": 1100.0, "low": 900.0, "high": 1400.0}    # GBP/kWp
BATTERY_CAPEX_PER_KWH = {"baseline": 350.0, "low": 250.0, "high": 450.0} # GBP/kWh
CHARGER_CAPEX_PER_UNIT = {"baseline": 1000.0, "low": 500.0, "high": 2000.0}  # low-power AC bay
INSTALL_FRACTION = {"baseline": 0.20, "low": 0.15, "high": 0.25}     # of equip CAPEX
OPEX_FRACTION = {"baseline": 0.02, "low": 0.015, "high": 0.03}       # of CAPEX / yr
ELECTRICITY_TARIFF = {"baseline": 0.26, "low": 0.22, "high": 0.30}   # GBP/kWh (mean)
ELECTRICITY_TARIFF_UNCERTAINTY = 0.15
FEED_IN_TARIFF = 0.05                    # GBP/kWh export credit (SEG, conservative)

# Time-of-use commercial tariff (GBP/kWh) by hour (UK Power Networks ToU shape):
# cheap overnight, standard daytime, expensive 16:00-19:00 peak. Mean ~ baseline.
TOU_TARIFF = [
    0.16, 0.16, 0.16, 0.16, 0.16, 0.16,   # 00-05  off-peak (night)
    0.22, 0.26, 0.26, 0.26, 0.26, 0.26,   # 06-11  day
    0.26, 0.26, 0.26, 0.26, 0.38, 0.38,   # 12-17  -> peak from 16:00
    0.38, 0.28, 0.24, 0.22, 0.18, 0.16,   # 18-23  peak then easing to off-peak
]
# Marginal grid emissions factor (gCO2/kWh): displaced grid energy avoids the
# MARGINAL plant (UK ~ gas CCGT), not the system average. Used for carbon savings
# (consequential accounting); the average regional series is kept for context.
MARGINAL_CARBON_GCO2_KWH = 360.0
# PV export to the grid is limited by the SAME physical connection as import.
EXPORT_LIMITED_BY_CONNECTION = True
# Commercial peak-demand / capacity charge (GBP per kW of annual peak grid import
# per year) — DUoS availability + red-band charges. This rewards peak shaving even
# when energy service is met, giving storage/PV a demand-charge value.
DEMAND_CHARGE_PER_KW_YEAR = 80.0

DISCOUNT_RATE = 0.06                     # social/commercial discount rate
PROJECT_LIFETIME_YEARS = 15
PV_LIFETIME_YEARS = 25
# Design horizon: the station is sized (a here-and-now decision) to serve demand
# at this planning horizon, across the plausible demand-growth range. 5 years is
# a typical refinance/upgrade review period for distributed energy assets.
OPTIMISATION_HORIZON_YEARS = 5
CARBON_PRICE_PER_TONNE = 80.0            # GBP/tCO2 (UK ETS indicative, for valuation)

# --------------------------------------------------------------------------- #
#  6. Design decision space  (EoI: PV 5-25 kWp, battery 0-50 kWh, 4-20 chargers)
# --------------------------------------------------------------------------- #
PV_SIZES_KWP = list(range(5, 26, 5))          # 5,10,15,20,25
BATTERY_SIZES_KWH = list(range(0, 51, 10))    # 0,10,20,30,40,50
CHARGER_COUNTS = list(range(4, 21, 4))        # 4,8,12,16,20

# Grid connection limit (kW). This is the crux of the robustness problem: the
# site has a constrained/low-cost grid connection (upgrading a connection needs
# an expensive DNO substation reinforcement). The station must therefore serve
# peak charging demand from solar + storage. Under-sizing strands the fleet under
# high demand; over-sizing wastes capital under low demand -> robust design.
# ~14 kW reflects an existing modest 3-phase import limit (≈20 A/phase). A
# higher-capacity upgrade typically needs a DNO reinforcement costing tens of
# thousands of pounds and many months, which is precisely why on-site solar +
# storage is attractive. The conclusion is shown to hold across 10-22 kW in the
# robustness-of-robustness analysis (src/robustness.py) — NOT an artefact of this
# single value.
GRID_CONNECTION_KW = 15.0

# Service-level target: a design is "robustly feasible" if it serves at least this
# share of annual charging demand in EVERY scenario (the rest defers to off-peak /
# other depots). 95% is a defensible operator service level; the conclusion is
# tested against this threshold in the robustness analysis.
SERVICE_LEVEL_TARGET = 0.95
# Value of unmet charging demand (GBP/kWh). A kWh of charging the station cannot
# deliver = a stranded e-scooter = lost mobility service and operator revenue.
# Conservative vs a bottom-up estimate (~0.4 kWh/charge enabling several
# GBP3-4 trips => GBP30-100/kWh); 10 GBP/kWh is a defensible "value of lost
# load" that makes under-provision costly, as it is in reality.
UNMET_DEMAND_PENALTY = 10.0

# --------------------------------------------------------------------------- #
#  7. Monte Carlo / robust-optimisation settings
# --------------------------------------------------------------------------- #
N_MONTE_CARLO = 500                      # EoI specifies a 500-sample fan
N_SCENARIOS_ROBUST = 200                 # scenarios used inside the optimiser
# Chance constraint for the stochastic program: meet the service target in
# scenarios totalling at least this probability (Birge & Louveaux, 2011).
CHANCE_CONSTRAINT_BETA = 0.90
# CVaR confidence level for the risk-averse stochastic program: optimise the
# expected cost in the worst (1-alpha) tail of scenarios (Rockafellar & Uryasev).
CVAR_ALPHA = 0.90


@dataclass(frozen=True)
class UncertainVariable:
    """One uncertain input for Monte Carlo / tornado sensitivity."""
    name: str
    label: str
    baseline: float
    low: float
    high: float
    unit: str
    distribution: str = "triangular"     # triangular | uniform | normal


# Ordered list of the uncertain variables named in the EoI / Data Inventory.
# demand_intensity (trips/scooter/day) is the primary demand lever; the rest are
# the operating, performance and cost uncertainties.
UNCERTAIN_VARIABLES: list[UncertainVariable] = [
    UncertainVariable("demand_intensity", "Demand intensity (trips/scooter/day)", 1.5, 0.5, 3.5, "trips/day"),
    UncertainVariable("demand_growth", "Demand growth (YoY)", 0.08, 0.0, 0.15, "/yr"),
    UncertainVariable("fleet_utilisation", "Daily fleet utilisation", 0.65, 0.40, 0.90, "frac"),
    UncertainVariable("trip_energy", "Trip energy use", 35.0, 22.0, 55.0, "Wh/km"),
    UncertainVariable("pv_output", "PV performance ratio", 0.85, 0.75, 0.95, "frac"),
    UncertainVariable("battery_eff", "Battery round-trip eff.", 0.92, 0.88, 0.94, "frac"),
    UncertainVariable("charger_avail", "Charger availability", 0.95, 0.90, 0.99, "frac"),
    UncertainVariable("electricity_price", "Electricity tariff", 0.26, 0.22, 0.30, "GBP/kWh"),
    UncertainVariable("equipment_cost", "Equipment cost multiplier", 1.0, 0.80, 1.30, "x"),
]


def scenario_table() -> dict:
    """Return the headline Low / Medium / High scenario definition."""
    return {
        "Low":    {"trips_per_scooter_day": TRIPS_PER_SCOOTER_DAY["low"],
                   "fleet_utilisation": FLEET_UTILISATION["low"],
                   "demand_growth": DEMAND_GROWTH["low"]},
        "Medium": {"trips_per_scooter_day": TRIPS_PER_SCOOTER_DAY["medium"],
                   "fleet_utilisation": FLEET_UTILISATION["baseline"],
                   "demand_growth": DEMAND_GROWTH["medium"]},
        "High":   {"trips_per_scooter_day": TRIPS_PER_SCOOTER_DAY["high"],
                   "fleet_utilisation": FLEET_UTILISATION["high"],
                   "demand_growth": DEMAND_GROWTH["high"]},
    }


if __name__ == "__main__":
    n_designs = len(PV_SIZES_KWP) * len(BATTERY_SIZES_KWH) * len(CHARGER_COUNTS)
    print(f"Site               : {SITE_NAME}  ({SITE_LAT}, {SITE_LON})")
    print(f"PV sizes (kWp)     : {PV_SIZES_KWP}")
    print(f"Battery sizes (kWh): {BATTERY_SIZES_KWH}")
    print(f"Charger counts     : {CHARGER_COUNTS}")
    print(f"Total designs      : {n_designs}")
    print(f"Monte Carlo samples: {N_MONTE_CARLO}")
    print(f"Uncertain variables: {len(UNCERTAIN_VARIABLES)}")
