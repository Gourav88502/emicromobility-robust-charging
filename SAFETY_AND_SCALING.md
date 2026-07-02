# Safety & Scalability Analysis

> Final-round criterion: **Scalability, Safety & Cost Analysis (10%)**. This
> document is the engineering back-up for the claims made on Slide 5 of the
> presentation and the *Scale · Safety · Cost* section of the live demo site.
> Cost analysis lives in the model itself (`src/economics.py`, every figure
> traceable to `src/config.py` sources); this file covers what the code cannot:
> physical safety and the scale-up path.

---

## 1. Safety case

### 1.1 Battery chemistry & storage (weak-grid variant only)

The recommended 15 kW-connected hub is **battery-free** — the safest battery
is the one you don't install, and it removes ~a third of potential CAPEX and
its embodied fire load in one decision. Where the grid sweep puts storage into
the design (connections **≤ ~9 kW**, e.g. off-grid or Indian distribution
feeders), we specify:

| Choice | Rationale |
|---|---|
| **LFP (LiFePO₄) cells** | No cobalt/nickel; thermal-runaway onset ≈ 270 °C vs ≈ 210 °C for NMC; O₂-poor decomposition — materially lower fire severity |
| Outdoor, free-standing IP54+ cabinet | ≥ 1 m clearance from buildings and bays; no shared wall with occupied space |
| Battery management system (BMS) | Cell-level voltage/temperature monitoring, over-charge/discharge lockout, thermal cut-off |
| ≤ 50 kWh per cabinet | Keeps the installation inside common insurer/DNO notification thresholds; larger sites replicate cabinets with spacing |

**Standards mapping (UK):**

- **BS EN 62485-5** — safety of stationary secondary-battery installations
- **BS EN 50604-1** — light-EV (e-bike/e-scooter) battery pack safety
- **BS EN IEC 62619** — industrial Li-ion cell/battery safety
- **PAS 7061 / PAS 7062** — safe handling, storage and charging of e-micromobility batteries (the post-2023 UK fire-safety guidance written for exactly this use case)

### 1.2 Charging bays & electrical installation

- **Low-power AC bays (3 kW)** — an order of magnitude below EV rapid chargers;
  each circuit protected by a **Type-B RCD** + MCB per **BS 7671** (18th ed.).
- **IP65-rated outdoor sockets/enclosures** under a ventilated canopy — packs
  charge sheltered from rain but never in an enclosed, occupied space, and
  away from building escape routes (LFB / Home Office e-bike fire guidance).
- **Smoke/heat detection** at the canopy + a dry riser-accessible location
  agreed with campus fire officers; signage for staff pack-handling (PAS 7061).
- Bays are physically spaced so a single-pack event cannot propagate along
  the rack (tested guidance from shared-fleet depot operators).

### 1.3 Peak-load safety — enforced twice

The grid cap is not an assumption, it is **enforced in two independent layers**:

1. **Software:** the smart-charging EMS schedules within the 15 kW envelope
   (the dispatch model shows peak import at, not above, the cap).
2. **Hardware:** the supply is fused/set at the connection agreement level, so
   even an EMS fault cannot overload the DNO connection.

### 1.4 Operational safety

- PV on a ground-mount/canopy frame — no roof work at height for cleaning.
- DC isolators + labelled AC/DC separation per MCS/IET Solar PV code.
- The Simulink digital twin (`matlab/chargingHubTwin.slx`) doubles as an
  operator-training and fault-injection sandbox before anything is energised.

---

## 2. Scalability analysis

### 2.1 Scale by replication, not reinforcement

One hub serves the ~360-bike UoW scheme with 8 bays and £29.4k CAPEX. Because
the binding constraint is the **grid connection**, the economic way to scale a
city fleet is **N modular hubs** rather than one big depot:

- No DNO reinforcement (tens of £k + months of lead time per site avoided).
- Hubs sit where the bikes already cluster — shorter rebalancing trips.
- Failure isolation: one hub down ≠ fleet down (service-level resilience).

### 2.2 Site-agnostic by construction

Re-siting the model is a **data swap, not a code change**:

| To re-size for a new site, change… | Where |
|---|---|
| Coordinates (solar) | `fetch_real_data.py` → live PVGIS pull |
| Demand history | drop the operator CSV into `data/raw/` |
| Grid connection & tariff | `src/config.py` (2 lines) |

The robustness sweep already covers 10–22 kW connections, 0.35–0.6 demand
share and five growth paths — most UK sites land inside the tested envelope.

### 2.3 UK ↔ India transfer (the Going Global context)

This competition is delivered under a **British Council UK–India partnership**
(Warwick, IIT Kharagpur, IIT BHU, SimLionics). The same pipeline transfers:

- **Solar:** Indian sites yield ~1,500–1,700 kWh/kWp·yr (vs 1,036 in Coventry)
  — PVGIS covers both; higher yield shrinks the PV array for the same service.
- **Fleet:** 2-wheeler/3-wheeler packs (1–3 kWh) replace 0.5 kWh e-bike packs —
  one constant in `config.py`.
- **Grid:** weaker/less reliable distribution feeders push sites **below the
  ~9 kW storage boundary — the battery + LFP safety case above becomes the
  binding design**, which is exactly why the boundary was worth locating.

### 2.4 What scaling does *not* change

The headline finding — *smart charging is the cheapest robustness lever;
storage pays only below ~9 kW of grid* — held in **100% of the 35
penalty × grid × horizon combinations** tested. Scaling changes the sizes,
not the shape, of the answer.

---

## 3. Cost analysis (pointer)

Full annualised cost model in `src/economics.py`:
annuitised CAPEX (6%, 15 yr) + O&M + DoD/calendar-aware battery replacement +
time-of-use grid energy + £80/kW·yr demand charge − export credit − PV
residual value. Headlines: **£29,400 CAPEX · £19,232/yr worst-case ·
LCOE £0.253/kWh · −59% worst-case vs naive**. See `outputs/results.json`
for the machine-readable numbers and the live site for the interactive
breakdown.
