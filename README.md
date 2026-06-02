# 🛴 Robust Charging Infrastructure Design under Demand Uncertainty

**Solar-powered shared e‑micromobility charging station — Newcastle upon Tyne**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-8%2F8%20passing-brightgreen.svg)](tests/test_pipeline.py)
[![CI](https://img.shields.io/badge/CI-build%20%26%20test-success.svg)](.github/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Reproducible](https://img.shields.io/badge/reproducible-one%20command-success.svg)](run_analysis.py)

> National Competition for Sustainable e‑Micromobility 2025‑26 · University of Warwick / British Council Going Global Partnerships
> **Theme 3 (primary)** — design of a solar‑PV charging station for a shared e‑bike/e‑scooter fleet
> **Theme 2 (secondary)** — modelling charge/discharge profiles under different demand scenarios
> **Institution:** Newcastle University

---

## 1. The problem in one sentence

> *A charging station sized for **average** demand fails when demand peaks; a station sized for the **worst case** wastes capital — so which station should you actually build?*

Shared e‑scooter charging demand in Newcastle swings with season, weather and growth. Worse, the site has a **constrained grid connection** (upgrading it needs an expensive network reinforcement), so the station must serve the evening charging peak from **solar + storage**. This project uses **robust optimisation** to pick the station specification that performs reliably across *every* plausible demand future — and quantifies what that robustness is worth.

## 2. Headline result

| | Naive (average‑demand) design | **Robust design (recommended)** |
|---|---|---|
| Specification | 5 kWp PV · 0 kWh battery · 4 chargers | **25 kWp PV · 50 kWh battery · 4 chargers** |
| Worst‑case annual cost | £52,619 / yr | **£21,045 / yr** |
| Guaranteed fleet service (worst demand) | 87.0 % | **98.9 %** |
| Chance of stranding fleet (Monte‑Carlo) | 8.4 % of futures | **0 %** |

### 🏆 Value of robustness: **−60 % worst‑case cost** and fleet service lifted **87 % → 99 %**

![Cost vs robustness Pareto frontier](outputs/02_pareto.png)

*The four decision rules trace the cost‑vs‑robustness trade‑off. The naive design is cheap on average but catastrophic in the worst case (top‑left); the robust **maximin** design sits at the bottom of the frontier — lowest worst‑case cost and the only fully robustly‑feasible choice.*

---

## 3. What the model does (pipeline)

![Methodology flow](outputs/methodology_flow.png)

1. **Demand scenarios (Low/Medium/High)** built from the **real** DfT Newcastle/Neuron e‑scooter monitoring data (Jan 2022 – May 2024).
2. **Hourly energy‑balance dispatch** over 8,760 hours: PV → demand → battery (with overnight grid top‑up for peak‑shaving) → capped grid → unmet. JIT‑compiled with Numba (~100× faster).
3. **Robust optimisation** of every PV (5–25 kWp) × battery (0–50 kWh) × charger (4–20) combination against 9 demand scenarios using **four decision rules**.
4. **Monte‑Carlo** uncertainty fan (500 correlated samples across 9 uncertain variables).
5. **Tornado** one‑at‑a‑time sensitivity analysis.
6. **Sustainability**: operational CO₂ savings vs grid‑only charging.

| Demand scenarios | Hourly dispatch & battery profile (Theme 2) |
|---|---|
| ![scenarios](outputs/01_scenario_demand.png) | ![dispatch](outputs/07_energy_balance.png) |

| Cost distribution (insurance premium) | Tornado sensitivity |
|---|---|
| ![cost](outputs/05_cost_distribution.png) | ![tornado](outputs/06_tornado.png) |

---

## 4. Quick start (3 commands)

```bash
# 1. clone and enter
git clone <your-repo-url> && cd emicromobility-robust-charging

# 2. install dependencies (Python 3.10+)
pip install -r requirements.txt

# 3. run the whole analysis end‑to‑end
python run_analysis.py
```

That single command **prepares the datasets, runs every model, and writes all figures and a combined report** to `outputs/`. It is deterministic (fixed seed) and self‑healing (it regenerates any missing data), so it works on a fresh clone in ~25 seconds.

That command also rebuilds the **methodology flow diagram** and the **2‑page anonymised
Executive Summary** (`outputs/Executive_Summary.docx`) used for the blind‑judged Level‑1 round.

**Then open the interactive report:**

```
outputs/index.html               ← interactive results, open in any browser
outputs/Executive_Summary.docx   ← 2-page anonymised summary (Level-1 submission)
```

### Interactive dashboard (stakeholder demo)

```bash
streamlit run dashboard/app.py
```

Move the sliders to design your own station and watch the energy balance, service level, cost and carbon respond live; explore the Pareto frontier, Monte‑Carlo fan and tornado interactively.

### Run the tests

```bash
python tests/test_pipeline.py        # or:  python -m pytest -q
```

### (Optional) use fully live API data

```bash
python scripts/fetch_real_data.py    # pulls real PVGIS + UK Carbon Intensity, then re-run run_analysis.py
```

---

## 5. Repository structure

```
emicromobility-robust-charging/
├── run_analysis.py            ← ONE command runs everything → outputs/
├── requirements.txt
├── README.md  ·  LICENSE  ·  REFERENCES.md  ·  .gitignore
│
├── src/                       ← the model (each file runs standalone for a demo)
│   ├── config.py              ← single source of truth for EVERY parameter
│   ├── demand_model.py        ← DfT data → hourly demand scenarios
│   ├── pv_model.py            ← PV generation from solar series
│   ├── energy_balance.py      ← 8,760‑hour dispatch engine (Numba‑accelerated)
│   ├── economics.py           ← CAPEX / OPEX / LCOE / battery replacement
│   ├── optimization.py        ← naive / stochastic / minimax‑regret / maximin
│   ├── monte_carlo.py         ← 500‑sample correlated uncertainty fan
│   ├── sensitivity.py         ← tornado one‑at‑a‑time analysis
│   ├── emissions.py           ← carbon savings vs grid‑only
│   └── visualize.py           ← all Plotly figures (one clean theme)
│
├── scripts/
│   ├── prepare_data.py            ← builds analysis‑ready datasets (real DfT + solar + carbon)
│   ├── fetch_real_data.py         ← optional live PVGIS / Carbon API pull
│   ├── make_flow_diagram.py       ← methodology flow diagram (the "Approach" figure)
│   └── build_executive_summary.py ← anonymised 2‑page Executive Summary (.docx)
│
├── dashboard/app.py           ← interactive Streamlit dashboard
├── tests/test_pipeline.py     ← 8 regression tests (physics + economics + pipeline)
├── .github/workflows/ci.yml   ← CI: install, test, run full pipeline on every push
│
├── data/
│   ├── raw/…dft…trials….ods   ← official DfT spreadsheet (real public data)
│   ├── data_inventory.xlsx    ← approved data inventory (30+ sources)
│   └── *.csv                  ← generated analysis‑ready datasets
└── outputs/                   ← all figures (.html + .png), report, results.json
```

---

## 6. Key parameters (all in [`src/config.py`](src/config.py))

| Lever | Range / value | Source |
|---|---|---|
| PV array | 5 – 25 kWp (sweep) | EoI design space |
| Battery storage | 0 – 50 kWh (sweep) | EoI design space |
| Charge points | 4 – 20 units (sweep) | EoI design space |
| Grid connection cap | **8 kW** | constrained‑connection assumption (the crux of the problem) |
| Demand intensity | 0.5 / 1.5 / 3.5 trips/scooter/day | DfT data + data inventory |
| Demand growth | 0 / 8 / 15 % per year | data inventory |
| PV CAPEX | £900 – £1,400 /kWp | BEIS, IRENA, Solar Trade Assoc. |
| Battery CAPEX | £250 – £450 /kWh | BloombergNEF, IRENA |
| Charger CAPEX | £1,500 – £5,000 /unit | OZEV, Zap‑Map |
| Electricity tariff | £0.22 – £0.30 /kWh | Ofgem |
| Trip energy | 20 – 35 Wh/km | Gössling (2020), Hollingsworth (2019) |

Nine uncertain variables are propagated through Monte‑Carlo and ranked by the tornado analysis. **Every figure in this README is regenerated by `run_analysis.py`** — nothing is hand‑drawn.

---

## 7. Data sources

| Dataset | Use | Provenance |
|---|---|---|
| **DfT shared e‑scooter trials monitoring data** | Low/Med/High demand scenarios | **Real** open government data (Newcastle/Neuron rows, Jan 2022–May 2024), bundled in `data/raw/` |
| **PVGIS (EU JRC)** | Hourly solar generation, Newcastle | Calibrated to PVGIS TMY (≈900 kWh/m²/yr); live pull available |
| **UK Carbon Intensity API (National Grid ESO)** | Operational CO₂ savings | NE‑England regional series (≈220 gCO₂/kWh) |
| Cost & performance benchmarks | CAPEX/OPEX/efficiency | BEIS, IRENA, BloombergNEF, OZEV, Zap‑Map, Fraunhofer ISE — see [`REFERENCES.md`](REFERENCES.md) |

---

## 8. Originality & academic integrity

This is **100 % original work** written for this competition:

- All model code, the dispatch engine, the optimisation formulation, and every figure were written from scratch for this project.
- The **only** external dataset redistributed is the **DfT e‑scooter monitoring spreadsheet** (UK Open Government Licence — free to reuse with attribution); it is unmodified in `data/raw/`.
- Solar and carbon series are **physically modelled and calibrated** to published reference values, not copied; a live‑API path is provided for genuine pulls.
- Every numeric assumption carries an inline source comment in `config.py`, and all literature is cited in `REFERENCES.md`.
- No text or code was copied from third parties. The repository is self‑contained and fully reproducible, supporting the competition's AI/plagiarism checks.

---

## 9. Team

| Member | Role |
|---|---|
| **Gourav Singh** | Solar PV & Charging Infrastructure Specialist |
| **Neelesh Raj** | Robust Optimisation & Simulation Developer |
| **Priti Burud** | Demand Uncertainty Analyst & Sustainability Evaluator |

*Newcastle University — Sustainable e‑Micromobility Futures.*

## 10. License

Released under the [MIT License](LICENSE). DfT data © Crown copyright, reused under the Open Government Licence v3.0.
