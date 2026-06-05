# MATLAB / Simulink layer — operational modelling

This folder adds a **MATLAB + Simulink** study on top of the Python robust-sizing
model. Python decides *what to build* (robust PV + bays under uncertainty);
MATLAB/Simulink shows *how to operate it* — and validates it with a digital twin.
Everything reads the **same real datasets** (`../data/`) so the two layers agree.

## What it does (one master script, four parts)

| Part | File | Output |
|---|---|---|
| **1. Fleet-load simulation** | `opt1_fleet_load.m` | Charging load, peak (kW) and energy (kWh) for **50 / 100 / 500** vehicles |
| **2. Smart-charging optimisation (LP)** | `opt2_smart_charging_lp.m` | `linprog` schedule that cuts **peak ≈ 35 %** and **cost ≈ 41 %** vs unmanaged |
| **3. Solar + battery energy management** | `opt3_solar_battery_ems.m` | PV + battery dispatch, solar self-consumption, battery state-of-charge |
| **4. Simulink digital twin** | `opt4_simulink_twin.m` | Auto-built Simulink model, validated against Part 3 (**0.00 % error**) |

Figures and a summary are written to `../outputs/matlab/`.

## How to run

**One click (Windows):** double-click **`RUN_MATLAB.bat`** in the project root.

**From the MATLAB app:**
```matlab
cd matlab
run_matlab_study
```

**Headless (no GUI):**
```bash
matlab -batch "cd('matlab'); run_matlab_study"
```

Requires: MATLAB + **Optimization Toolbox** (for `linprog`) + **Simulink**
(R2026a used here). Run the Python pipeline first (or just clone the repo — the
real data CSVs are committed) so `../data/` exists.

## Outputs
- `matlab_opt1_fleet_load.png` — load profiles by fleet size
- `matlab_opt2_smart_charging.png` — unmanaged vs LP-optimal charging + ToU tariff
- `matlab_opt3_solar_battery.png` — PV/battery/grid power flows + SoC
- `matlab_opt4_digital_twin.png` — Simulink twin vs MATLAB EMS (validation)
- `chargingHubTwin.slx` — the generated Simulink model
- `matlab_summary.txt` — all headline numbers

---

## CV / application statements (for renewable-energy PhD applications)

> *Developed MATLAB simulations of shared e‑micromobility charging demand across
> fleet sizes (50–500 vehicles) using real DfT trial data, quantifying peak load,
> energy demand and grid impact.*

> *Implemented and evaluated **smart‑charging optimisation** with MATLAB's
> Optimization Toolbox (linear programming, time‑of‑use scheduling), reducing
> peak demand by ~35 % and electricity cost by ~41 %.*

> *Modelled an **integrated solar‑PV + battery‑storage + charging** system in
> MATLAB/Simulink and analysed energy‑management performance (solar
> self‑consumption and battery state of charge).*

> *Built a **Simulink digital twin** of the charging hub (PV, battery, load,
> grid) and validated it against the optimisation model to <0.01 % error —
> demonstrating modelling, validation and systems thinking.*

**Combined one‑liner:** *Built an integrated MATLAB/Simulink model of a
solar‑powered e‑micromobility charging hub — fleet‑load simulation, linear‑
programming smart‑charging optimisation, solar‑plus‑battery energy management,
and a validated Simulink digital twin — on real UK open data.*
