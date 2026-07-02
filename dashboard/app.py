"""
app.py — Interactive Streamlit dashboard
=========================================
Stakeholder demonstration tool for the robust charging-station design model.

Run from the project root:
    streamlit run dashboard/app.py

Tabs
----
  1. Overview          – headline result & KPIs
  2. Station designer  – live "what-if": move the sliders, watch the energy
                         balance, service level, cost and carbon respond
  3. Robust optimiser  – Pareto frontier + five decision rules + value of robustness
  4. Uncertainty       – Monte-Carlo demand fan and cost distribution
  5. Sensitivity       – tornado chart
  6. Data & method     – datasets, assumptions and methodology
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import (config, demand_model, pv_model, economics, optimization,
                 monte_carlo, sensitivity, emissions, visualize)
from src.energy_balance import simulate
from src.economics import Design

st.set_page_config(page_title="Robust e-Micromobility Charging Station",
                   page_icon="🛴", layout="wide")


# --------------------------------------------------------------------------- #
#  Cached loaders (data prep is automatic on first run)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _bootstrap():
    needed = ["uow_bikes_demand.csv", "pvgis_warwick_hourly.csv",
              "carbon_intensity_west_midlands.csv"]
    if not all((config.DATA_DIR / f).exists() for f in needed):
        sys.path.insert(0, str(ROOT / "scripts"))
        import prepare_data
        prepare_data.main()
    return (demand_model.load_demand(), pv_model.load_solar(), emissions.load_carbon())


@st.cache_data(show_spinner="Running robust optimisation (150 designs × 15 scenarios)…")
def _optimise():
    return optimization.run_full_optimisation()


@st.cache_data(show_spinner="Running Monte-Carlo (500 samples)…")
def _monte_carlo(design_key, naive_key):
    df, solar, _ = _bootstrap()
    samples = monte_carlo.draw_samples()
    rec = Design(*design_key)
    nai = Design(*naive_key)
    return (monte_carlo.evaluate_design(rec, samples, df, solar),
            monte_carlo.evaluate_design(nai, samples, df, solar),
            samples)


df, solar, carbon = _bootstrap()
opt = _optimise()
rec_design = opt["rules"][opt["recommended_rule"]]["design"]
naive_design = opt["rules"]["naive_deterministic"]["design"]
vor = opt["value_of_robustness"]


# --------------------------------------------------------------------------- #
#  Header
# --------------------------------------------------------------------------- #
st.title("🛴 Robust Charging Infrastructure Design under Demand Uncertainty")
st.caption(f"Solar-powered shared e-micromobility charging station · {config.SITE_NAME} "
           f"· National Competition for Sustainable e-Micromobility 2025-26")

tab_over, tab_design, tab_thresh, tab_opt, tab_unc, tab_sens, tab_data = st.tabs(
    ["📌 Overview", "🎛️ Station designer", "🔋 Battery threshold", "🛡️ Robust optimiser",
     "🎲 Uncertainty", "🌪️ Sensitivity", "📚 Data & method"])


# --------------------------------------------------------------------------- #
#  Tab 1 — Overview
# --------------------------------------------------------------------------- #
with tab_over:
    st.subheader("Recommended robust station specification")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solar PV array", f"{rec_design.pv_kwp:g} kWp")
    c2.metric("Battery storage", f"{rec_design.battery_kwh:g} kWh")
    c3.metric("Charge points", f"{rec_design.n_chargers:g} units")
    c4.metric("Capital cost", f"£{economics.capex(rec_design)['total']:,.0f}")

    st.subheader("Why robust design pays")
    c1, c2, c3 = st.columns(3)
    c1.metric("Worst-case cost vs naive",
              f"-{vor['worst_cost_reduction_pct']:.0f}%",
              f"-£{vor['worst_cost_reduction']:,.0f}/yr")
    c2.metric("Guaranteed fleet service (worst case)",
              f"{vor['robust_min_service']*100:.0f}%",
              f"vs {vor['naive_min_service']*100:.0f}% naive")
    c3.metric("Robustly-feasible designs",
              f"{opt['robust_feasible_count']} / {opt['n_designs']}")

    st.info(
        f"A station sized for **average demand** (naive) is cheapest in normal "
        f"conditions but **strands up to {100-vor['naive_min_service']*100:.0f}% of the "
        f"fleet** under high demand. The robust design guarantees "
        f"{vor['robust_min_service']*100:.0f}% service across **all** plausible "
        f"futures while **cutting worst-case cost by "
        f"{vor['worst_cost_reduction_pct']:.0f}%**.")

    st.plotly_chart(visualize.fig_pareto(opt), use_container_width=True)


# --------------------------------------------------------------------------- #
#  Tab 2 — Interactive station designer
# --------------------------------------------------------------------------- #
with tab_design:
    st.subheader("Design your own station and stress-test it")
    left, right = st.columns([1, 2])
    with left:
        pv_kwp = st.select_slider("Solar PV (kWp)", config.PV_SIZES_KWP,
                                  value=rec_design.pv_kwp)
        batt = st.select_slider("Battery storage (kWh)", config.BATTERY_SIZES_KWH,
                                value=rec_design.battery_kwh)
        chargers = st.select_slider("Charge points", config.CHARGER_COUNTS,
                                    value=rec_design.n_chargers)
        scenario = st.radio("Demand scenario", ["Low", "Medium", "High"], index=2,
                            horizontal=True)
        grid_kw = st.slider("Grid connection limit (kW)", 4, 30,
                            int(config.GRID_CONNECTION_KW))
        horizon = st.slider("Demand horizon (years out)", 0,
                            config.PROJECT_LIFETIME_YEARS,
                            config.OPTIMISATION_HORIZON_YEARS)

    design = Design(pv_kwp, batt, chargers)
    params = demand_model.scenario_params(scenario, horizon)
    demand = demand_model.hourly_demand_series(params, df)
    pv = pv_model.pv_generation(pv_kwp, solar=solar)
    sim = simulate(design, demand, pv, grid_kw=grid_kw)
    costs = economics.annual_costs(design, sim)
    emis = emissions.emissions_analysis(sim, carbon)

    with right:
        m1, m2, m3, m4 = st.columns(4)
        svc = sim["service_level"] * 100
        m1.metric("Fleet service level", f"{svc:.1f}%",
                  "meets target" if svc >= config.SERVICE_LEVEL_TARGET*100 else "FAILS target",
                  delta_color="normal" if svc >= config.SERVICE_LEVEL_TARGET*100 else "inverse")
        m2.metric("Solar fraction", f"{sim['solar_fraction']*100:.0f}%")
        m3.metric("Annual cost", f"£{costs['total_annual_cost']:,.0f}")
        m4.metric("Carbon saving", f"{emis['carbon_saving_tCO2_yr']:.1f} t/yr")
        if svc < config.SERVICE_LEVEL_TARGET * 100:
            st.error(f"⚠️ This design strands {100-svc:.1f}% of charging demand "
                     f"({sim['unmet_demand_kwh']:,.0f} kWh/yr) in the {scenario} scenario.")
        else:
            st.success(f"✅ This design serves {svc:.1f}% of demand in the {scenario} scenario.")

    st.plotly_chart(visualize.fig_energy_balance(sim), use_container_width=True)
    st.plotly_chart(visualize.fig_energy_sources(sim, emis), use_container_width=True)


# --------------------------------------------------------------------------- #
#  Tab 3 — Battery threshold (the one-slider stakeholder demo)
# --------------------------------------------------------------------------- #
with tab_thresh:
    st.subheader("When does a battery pay? Move one slider.")
    st.markdown(
        "At the site's **15 kW connection the robust design carries no battery** — "
        "smart charging keeps the load under the limit. Weaken the connection and "
        "watch storage enter the optimal design.")

    thr_path = config.OUTPUT_DIR / "grid_battery_threshold.csv"
    if thr_path.exists():
        thr = pd.read_csv(thr_path).sort_values("grid_kW")
        g = st.slider("Grid connection limit (kW)", int(thr["grid_kW"].min()),
                      int(thr["grid_kW"].max()), int(config.GRID_CONNECTION_KW),
                      help="The robust (maximin) design at each grid limit, "
                           "precomputed by src/robustness.py")
        row = thr.iloc[(thr["grid_kW"] - g).abs().argsort().iloc[0]]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nearest swept grid limit", f"{row['grid_kW']:g} kW")
        c2.metric("Solar PV", f"{row['pv_kwp']:g} kWp")
        c3.metric("Battery in robust design", f"{row['battery_kwh']:g} kWh",
                  "storage pays here" if row["battery_kwh"] > 0 else "no battery needed",
                  delta_color="normal" if row["battery_kwh"] > 0 else "off")
        c4.metric("Charge bays", f"{row['n_chargers']:g}")

        st.bar_chart(thr.set_index("grid_kW")["battery_kwh"],
                     x_label="grid connection limit (kW)",
                     y_label="battery in robust design (kWh)")
        if row["battery_kwh"] > 0:
            st.warning(
                f"At **{row['grid_kW']:g} kW** the connection is too weak for smart "
                "charging alone — the optimiser buys storage to shift solar into the "
                "overnight load. For these weak-grid sites we specify LFP chemistry "
                "with second-life reuse (see SAFETY_AND_SCALING.md).")
        else:
            st.success(
                f"At **{row['grid_kW']:g} kW** smart charging alone keeps the load "
                "under the connection limit — a battery would add cost, degradation "
                "and embodied materials without improving service. The most "
                "sustainable battery is sometimes the one you do not need to install.")
        st.caption("Battery enters the robust design at ≤8 kW and is gone by 10 kW — "
                   "the storage boundary sits around 8–10 kW for this site.")
    else:
        st.info("Run `python run_analysis.py` (or `python scripts/grid_threshold_sweep.py`) "
                "to generate outputs/grid_battery_threshold.csv first.")


# --------------------------------------------------------------------------- #
#  Tab 4 — Robust optimiser
# --------------------------------------------------------------------------- #
with tab_opt:
    st.subheader("Five decision rules compared")
    rows = []
    for rule, info in opt["rules"].items():
        d = info["design"]
        rows.append({
            "Decision rule": visualize.RULE_LABELS[rule],
            "PV (kWp)": d.pv_kwp, "Battery (kWh)": d.battery_kwh, "Chargers": d.n_chargers,
            "Expected £/yr": round(info["expected_cost"]),
            "Worst-case £/yr": round(info["worst_cost"]),
            "Max regret £/yr": round(info["max_regret"]),
            "Min service %": round(info["min_service"]*100, 1),
            "Robust?": "✅" if info["robustly_feasible"] else "❌",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.plotly_chart(visualize.fig_design_comparison(opt), use_container_width=True)
    st.plotly_chart(visualize.fig_pareto(opt), use_container_width=True)


# --------------------------------------------------------------------------- #
#  Tab 4 — Uncertainty
# --------------------------------------------------------------------------- #
with tab_unc:
    st.subheader(f"Monte-Carlo uncertainty fan ({config.N_MONTE_CARLO} samples)")
    mc_rob, mc_nai, samples = _monte_carlo(rec_design.key, naive_design.key)
    monthly = np.array([
        demand_model.monthly_demand_series(
            demand_model.DemandParams(s.demand_intensity, s.fleet_utilisation,
                                      s.trip_energy, s.demand_growth,
                                      config.OPTIMISATION_HORIZON_YEARS), df)
        for s in samples])
    st.plotly_chart(visualize.fig_demand_fan(monthly), use_container_width=True)
    st.plotly_chart(visualize.fig_cost_distribution(mc_nai, mc_rob),
                    use_container_width=True)
    c1, c2 = st.columns(2)
    c1.metric("Robust P95 cost", f"£{mc_rob['annual_cost'].quantile(.95):,.0f}",
              f"meets target {(mc_rob['service_level']>=config.SERVICE_LEVEL_TARGET).mean()*100:.0f}% of the time")
    c2.metric("Naive P95 cost", f"£{mc_nai['annual_cost'].quantile(.95):,.0f}",
              f"strands fleet {(mc_nai['unmet_kwh']>1).mean()*100:.0f}% of the time",
              delta_color="inverse")


# --------------------------------------------------------------------------- #
#  Tab 5 — Sensitivity
# --------------------------------------------------------------------------- #
with tab_sens:
    st.subheader("Tornado sensitivity — what drives the cost of the robust design?")
    metric = st.selectbox("Output to test",
                          ["annual_cost", "service_level", "unmet_kwh"], index=0)
    tor = sensitivity.tornado(rec_design, df, solar, output=metric)
    label = {"annual_cost": "Annual cost (£/yr)", "service_level": "Service level",
             "unmet_kwh": "Unmet demand (kWh)"}[metric]
    st.plotly_chart(visualize.fig_tornado(tor, label), use_container_width=True)
    st.dataframe(tor[["variable", "low_input", "high_input", "unit",
                      "low_output", "high_output", "swing"]],
                 use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
#  Tab 6 — Data & method
# --------------------------------------------------------------------------- #
with tab_data:
    st.subheader("Datasets")
    st.markdown(f"""
- **UoW Bikes shared e-bike demand** — monthly trips, fleet size, trips/bike/day,
  trip distance & duration. Auto-ingests the official `UoW Bikes Data(Sheet1).csv`
  if placed in `data/raw/`; otherwise a calibrated representative series is used.
- **PVGIS solar (REAL, live API)** — hourly generation for Coventry
  (lat {config.SITE_LAT}, lon {config.SITE_LON}), ≈1036 kWh/kWp/yr.
- **Carbon intensity (REAL, live API)** — National Grid ESO regional series for
  {config.CARBON_REGION_NAME} (≈222 gCO₂/kWh mean).
""")
    st.subheader("Method")
    st.markdown("""
1. Build **Low / Medium / High × growth** demand scenarios from the UoW Bikes data.
2. **Hourly energy-balance** dispatch over 8,760 h with a *constrained grid
   connection* (PV → battery → capped grid, off-peak battery top-up).
3. **Robust optimisation** of 150 designs × 15 scenarios via five rules: naive,
   two-stage **stochastic program**, **CVaR**, **minimax regret**, **maximin**.
4. **Monte-Carlo** (500 correlated samples) for the demand & cost fan.
5. **Tornado** + variance-based **global (Sobol)** sensitivity.
6. **Robustness-of-robustness** sweep + benchmark **validation**.
""")
    st.subheader("Headline scenario demand (from real Coventry data)")
    st.dataframe(demand_model.scenario_summary(), use_container_width=True, hide_index=True)
    st.caption("All assumptions live in `src/config.py`; every figure is reproducible "
               "via `python run_analysis.py`.")
