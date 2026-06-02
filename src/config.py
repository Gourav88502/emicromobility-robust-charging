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
# Low / Medium / High daily trips-per-scooter (Data Inventory, row "Trips per
# scooter per day": Low 0.5 / Medium 1.5 / High 3.5). Real Newcastle range
# observed in the DfT data is 0.78-2.34; we widen to the literature envelope.
TRIPS_PER_SCOOTER_DAY = {"low": 0.5, "medium": 1.5, "high": 3.5}

# Trip energy consumption — Gossling (2020), Hollingsworth (2019).
TRIP_ENERGY_WH_PER_KM = {"baseline": 25.0, "low": 20.0, "high": 35.0}
TRIP_ENERGY_UNCERTAINTY = 0.30          # +/-30 % for Monte Carlo

# Daily fleet utilisation (fraction of fleet needing a charge each day).
FLEET_UTILISATION = {"baseline": 0.65, "low": 0.40, "high": 0.90}
FLEET_UTILISATION_UNCERTAINTY = 0.25

# Year-on-year demand growth (Data Inventory: 0 / 8 / 15 % per year).
DEMAND_GROWTH = {"low": 0.0, "medium": 0.08, "high": 0.15}

# Battery capacity of one e-scooter (Wh) — used to convert energy to "charges".
SCOOTER_BATTERY_WH = 500.0              # ~0.5 kWh typical shared e-scooter pack

# Share of the city fleet's charging demand captured by THIS solar hub. Newcastle
# runs ~700 shared e-scooters; one solar charging hub serves a portion of them
# (operators also swap/charge at depots and other points). Combined with the
# uncertain daily fleet utilisation this sets the station's energy demand to a
# range well matched to the 5-25 kWp / 0-50 kWh design space.
STATION_DEMAND_SHARE = 0.50

# Hourly demand shape: fraction of daily charging energy drawn each hour.
# Shared e-scooter operators collect depleted units and charge them in a
# concentrated evening window (18:00-22:00), with a smaller overnight depot
# top-up. This peakiness is what makes battery storage valuable under a capped
# grid connection. 24 weights, normalised to sum to 1.0 in the demand model.
HOURLY_DEMAND_SHAPE = [
    0.015, 0.010, 0.008, 0.008, 0.010, 0.015,   # 00-05  overnight depot top-up
    0.020, 0.025, 0.030, 0.025, 0.020, 0.020,   # 06-11
    0.022, 0.022, 0.022, 0.028, 0.045, 0.080,   # 12-17
    0.120, 0.135, 0.115, 0.085, 0.050, 0.030,   # 18-23  evening collection peak
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

# --------------------------------------------------------------------------- #
#  4. EV / e-scooter charge points  (OZEV / Rolec / Pod Point / Kempower)
# --------------------------------------------------------------------------- #
CHARGER_POWER_KW = {"baseline": 7.0, "low": 7.0, "high": 22.0}   # AC Type 2
CHARGER_AVAILABILITY = {"baseline": 0.95, "low": 0.90, "high": 0.99}

# --------------------------------------------------------------------------- #
#  5. Cost assumptions  (BEIS / IRENA / BloombergNEF / OZEV / Zap-Map / STA)
# --------------------------------------------------------------------------- #
PV_CAPEX_PER_KWP = {"baseline": 1100.0, "low": 900.0, "high": 1400.0}    # GBP/kWp
BATTERY_CAPEX_PER_KWH = {"baseline": 350.0, "low": 250.0, "high": 450.0} # GBP/kWh
CHARGER_CAPEX_PER_UNIT = {"baseline": 3000.0, "low": 1500.0, "high": 5000.0}
INSTALL_FRACTION = {"baseline": 0.20, "low": 0.15, "high": 0.25}     # of equip CAPEX
OPEX_FRACTION = {"baseline": 0.02, "low": 0.015, "high": 0.03}       # of CAPEX / yr
ELECTRICITY_TARIFF = {"baseline": 0.26, "low": 0.22, "high": 0.30}   # GBP/kWh
ELECTRICITY_TARIFF_UNCERTAINTY = 0.15
FEED_IN_TARIFF = 0.05                    # GBP/kWh export credit (SEG, conservative)

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
# 8 kW reflects a minimal single-phase commercial connection (no costly upgrade).
GRID_CONNECTION_KW = 8.0

# Service-level target: a design is "feasible" if it serves at least this share
# of annual charging-energy demand from the station (PV + battery + capped grid).
SERVICE_LEVEL_TARGET = 0.98
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
    UncertainVariable("trip_energy", "Trip energy use", 25.0, 20.0, 35.0, "Wh/km"),
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
