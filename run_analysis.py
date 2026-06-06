"""
run_analysis.py
===============
END-TO-END PIPELINE for the project. One command runs everything and writes all
deliverables to outputs/:

    python run_analysis.py

Steps
-----
  0. Prepare datasets (real DfT + calibrated solar/carbon) if missing.
  1. Build Low/Medium/High demand scenarios (with weekday/weekend distinction).
  2. Robust optimisation: 150 designs x 9 scenarios -> 5 decision rules,
     Pareto frontier, value of robustness. Each design evaluated under
     OPTIMAL LP dispatch (rolling-horizon, scipy HiGHS) — the coupled
     LP+sizing pipeline (Silvente et al. 2018; Morales-España et al. 2014).
  3. Monte-Carlo uncertainty fan (500 correlated samples) with bootstrap 95%
     confidence intervals on P05/P50/P95 cost and service-level probability.
  4. Tornado OAT + global Sobol sensitivity with bootstrap CIs on each index.
  5. Hourly LP-optimal dispatch + emissions for the recommended design.
  6. Generate all interactive figures (HTML + PNG) and a single combined report.
  7. Save machine-readable results.json and a plain-text executive summary.

The script is deterministic (fixed seed) and self-healing (regenerates data),
so it runs cleanly on a fresh clone with `pip install -r requirements.txt`.
"""

from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import (config, demand_model, pv_model, economics, optimization,
                 monte_carlo, sensitivity, emissions, visualize, robustness,
                 validation)
from src.energy_balance import simulate

ROOT = Path(__file__).resolve().parent
OUT = config.OUTPUT_DIR


def _ensure_data():
    needed = ["dft_newcastle_scooter_data.csv", "pvgis_newcastle_hourly.csv",
              "carbon_intensity_ne_england.csv"]
    if not all((config.DATA_DIR / f).exists() for f in needed):
        print("Datasets missing -> generating via scripts/prepare_data.py ...")
        sys.path.insert(0, str(ROOT / "scripts"))
        import prepare_data
        prepare_data.main()


def _save_fig(fig, name: str):
    html = OUT / f"{name}.html"
    fig.write_html(str(html), include_plotlyjs="cdn", full_html=True)
    try:
        fig.write_image(str(OUT / f"{name}.png"), width=1100, height=fig.layout.height or 500,
                        scale=2)
    except Exception as e:                       # kaleido optional
        print(f"   (PNG export skipped for {name}: {e})")
    return html.name


def main():
    t0 = time.time()
    print("=" * 72)
    print(" ROBUST CHARGING INFRASTRUCTURE DESIGN UNDER DEMAND UNCERTAINTY")
    print(" Newcastle University | Sustainable e-Micromobility Competition")
    print("=" * 72)
    _ensure_data()

    df = demand_model.load_dft()
    solar = pv_model.load_solar()
    carbon = emissions.load_carbon()
    figs = {}

    # ---- 1. Scenarios ------------------------------------------------------ #
    print("\n[1] Building Low/Medium/High demand scenarios ...")
    scen_summary = demand_model.scenario_summary()
    print(scen_summary.to_string(index=False))
    figs["01_scenario_demand"] = _save_fig(
        visualize.fig_scenario_demand(scen_summary), "01_scenario_demand")

    # ---- 2. Robust optimisation ------------------------------------------- #
    print("\n[2] Robust optimisation (150 designs x 9 scenarios, LP optimal dispatch) ...")
    opt = optimization.run_full_optimisation(df, solar)
    print(f"    Dispatch method: {opt.get('dispatch_method', 'unknown')}")
    print(f"    Robustly feasible designs: {opt['robust_feasible_count']}/{opt['n_designs']}")
    for rule, info in opt["rules"].items():
        flag = "robust" if info["robustly_feasible"] else "FAILS high demand"
        print(f"    {visualize.RULE_LABELS[rule]:28s}: {info['design']}  "
              f"[worst GBP{info['worst_cost']:,.0f} | min-svc {info['min_service']*100:.1f}% | {flag}]")
    vor = opt["value_of_robustness"]
    print(f"    VALUE OF ROBUSTNESS: worst-case cost -GBP{vor['worst_cost_reduction']:,.0f}/yr "
          f"({vor['worst_cost_reduction_pct']:.1f}%) and fleet service "
          f"{vor['naive_min_service']*100:.1f}% -> {vor['robust_min_service']*100:.1f}%")
    figs["02_pareto"] = _save_fig(visualize.fig_pareto(opt), "02_pareto")
    figs["03_design_comparison"] = _save_fig(
        visualize.fig_design_comparison(opt), "03_design_comparison")

    recommended = opt["rules"]["maximin_robust"]["design"]
    naive = opt["rules"]["naive_deterministic"]["design"]

    # ---- 3. Monte-Carlo fan ------------------------------------------------ #
    print(f"\n[3] Monte-Carlo uncertainty fan ({config.N_MONTE_CARLO} samples) ...")
    samples = monte_carlo.draw_samples()
    mc_robust = monte_carlo.evaluate_design(recommended, samples, df, solar)
    mc_naive = monte_carlo.evaluate_design(naive, samples, df, solar)
    s_rob = monte_carlo.summarise(mc_robust)
    s_nai = monte_carlo.summarise(mc_naive)
    ci_r = s_rob.get('ci_cost_p95', (0, 0))
    ci_n = s_nai.get('ci_cost_p95', (0, 0))
    print(f"    Robust  : E[cost] GBP{s_rob['cost_mean']:,.0f} | "
          f"P95 GBP{s_rob['cost_p95']:,.0f} [95%CI: {ci_r[0]:,.0f}-{ci_r[1]:,.0f}] "
          f"| P(meet target) {s_rob['prob_meets_target']*100:.0f}%")
    print(f"    Naive   : E[cost] GBP{s_nai['cost_mean']:,.0f} | "
          f"P95 GBP{s_nai['cost_p95']:,.0f} [95%CI: {ci_n[0]:,.0f}-{ci_n[1]:,.0f}] "
          f"| P(meet target) {s_nai['prob_meets_target']*100:.0f}%")

    monthly = np.array([
        demand_model.monthly_demand_series(
            demand_model.DemandParams(
                s.demand_intensity, s.fleet_utilisation,
                s.trip_energy, s.demand_growth, config.OPTIMISATION_HORIZON_YEARS), df)
        for s in samples])
    figs["04_demand_fan"] = _save_fig(visualize.fig_demand_fan(monthly), "04_demand_fan")
    figs["05_cost_distribution"] = _save_fig(
        visualize.fig_cost_distribution(mc_naive, mc_robust), "05_cost_distribution")

    # ---- 4. Sensitivity: tornado (OAT) + global Sobol --------------------- #
    print("\n[4] Sensitivity analysis (recommended design) ...")
    tor = sensitivity.tornado(recommended, df, solar, output="annual_cost")
    print(f"    Tornado top driver : {tor.iloc[0]['variable']} (swing GBP{tor.iloc[0]['swing']:,.0f})")
    figs["06_tornado"] = _save_fig(visualize.fig_tornado(tor), "06_tornado")
    sob = sensitivity.global_sensitivity(recommended, df, solar, output="annual_cost", n=2048)
    print(f"    Global Sobol top   : {sob.iloc[0]['variable']} "
          f"({sob.iloc[0]['pct_total']:.0f}% of cost variance, total-effect)")
    figs["09_global_sensitivity"] = _save_fig(
        visualize.fig_global_sensitivity(sob), "09_global_sensitivity")

    # ---- 4b. Robustness-of-robustness (is the conclusion an artefact?) ----- #
    print("\n[4b] Robustness-of-robustness (penalty x grid x horizon) ...")
    rob = robustness.sweep(df, solar)
    print("     " + robustness.summary_text(rob))
    figs["10_robustness"] = _save_fig(visualize.fig_robustness_heatmap(rob), "10_robustness")

    # ---- 4c. Validation against published benchmarks ----------------------- #
    print("\n[4c] Validation against published benchmarks ...")
    val = validation.validate(df, solar, carbon, recommended)
    print(f"     {int(val['within_range'].sum())}/{len(val)} metrics within published range")
    figs["11_validation"] = _save_fig(visualize.fig_validation(val), "11_validation")

    # ---- 5. Dispatch + emissions ------------------------------------------ #
    print("\n[5] Hourly energy-balance dispatch & emissions (recommended design) ...")
    demand_hi = demand_model.hourly_demand_series(
        demand_model.scenario_params("High", config.OPTIMISATION_HORIZON_YEARS), df)
    pv_rec = pv_model.pv_generation(recommended.pv_kwp, solar=solar)
    sim = simulate(recommended, demand_hi, pv_rec)
    emis = emissions.emissions_analysis(sim, carbon)
    print(f"    Service {sim['service_level']*100:.1f}% | solar fraction "
          f"{sim['solar_fraction']*100:.1f}% | carbon saving "
          f"{emis['carbon_saving_tCO2_yr']:.1f} tCO2/yr ({emis['carbon_saving_pct']:.0f}%)")
    figs["07_energy_balance"] = _save_fig(
        visualize.fig_energy_balance(sim), "07_energy_balance")
    figs["08_energy_sources"] = _save_fig(
        visualize.fig_energy_sources(sim, emis), "08_energy_sources")

    # ---- 6. Persist results ------------------------------------------------ #
    print("\n[6] Writing results.json, executive summary and combined report ...")
    results = _collect_results(opt, s_rob, s_nai, tor, sob, sim, emis, recommended, naive,
                               rob, val)
    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    _write_summary(results)
    _write_report(figs, results)

    # tidy CSVs for the repo / dashboard
    scen_summary.to_csv(OUT / "scenario_summary.csv", index=False)
    opt["pareto"].to_csv(OUT / "pareto_frontier.csv", index=False)
    tor.to_csv(OUT / "tornado_sensitivity.csv", index=False)
    sob.to_csv(OUT / "global_sensitivity_sobol.csv", index=False)
    val.to_csv(OUT / "validation_benchmarks.csv", index=False)
    rob["horizon_table"].to_csv(OUT / "robustness_horizon_sweep.csv", index=False)
    mc_robust.to_csv(OUT / "monte_carlo_robust.csv", index=False)
    mc_naive.to_csv(OUT / "monte_carlo_naive.csv", index=False)

    # ---- 7. Methodology flow diagram + anonymised executive summary -------- #
    print("\n[7] Building methodology flow diagram and executive summary ...")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import make_flow_diagram
        make_flow_diagram.main()
    except Exception as e:
        print(f"   (flow diagram skipped: {e})")
    try:
        import build_executive_summary
        build_executive_summary.build()
    except Exception as e:
        print(f"   (executive summary skipped — needs python-docx: {e})")
    try:
        import build_presentation
        build_presentation.build()
    except Exception as e:
        print(f"   (presentation skipped — needs python-pptx: {e})")

    print(f"\nDONE in {time.time()-t0:.1f}s. All outputs in: {OUT}")
    print(f"Open the report: {OUT / 'index.html'}")


def _collect_results(opt, s_rob, s_nai, tor, sob, sim, emis, recommended, naive,
                     rob, val) -> dict:
    def design_dict(d):
        return {"pv_kwp": d.pv_kwp, "battery_kwh": d.battery_kwh, "n_chargers": d.n_chargers}
    cap = economics.capex(recommended)
    return {
        "project": "Robust Charging Infrastructure Design Under Demand Uncertainty",
        "site": config.SITE_NAME,
        "grid_connection_kW": config.GRID_CONNECTION_KW,
        "design_horizon_years": config.OPTIMISATION_HORIZON_YEARS,
        "recommended_design": design_dict(recommended),
        "recommended_capex_gbp": round(cap["total"], 0),
        "naive_design": design_dict(naive),
        "decision_rules": {
            r: {"design": design_dict(info["design"]),
                "expected_cost": round(info["expected_cost"], 0),
                "worst_cost": round(info["worst_cost"], 0),
                "max_regret": round(info["max_regret"], 0),
                "min_service_pct": round(info["min_service"] * 100, 1),
                "prob_served_pct": round(info["prob_served"] * 100, 1),
                "robustly_feasible": info["robustly_feasible"]}
            for r, info in opt["rules"].items()},
        "value_of_robustness": {k: (round(v, 3) if isinstance(v, float) else v)
                                for k, v in opt["value_of_robustness"].items()},
        "monte_carlo": {
            "robust": {k: round(float(v), 1) for k, v in s_rob.items()},
            "naive": {k: round(float(v), 1) for k, v in s_nai.items()}},
        "top_sensitivities": tor[["variable", "swing"]].head(3).to_dict("records"),
        "global_sensitivity_sobol_total": sob[["variable", "pct_total"]].head(3).to_dict("records"),
        "robustness_of_robustness": {
            "fraction_robust_beats_naive_pct": round(rob["fraction_robust_wins"] * 100, 0),
            "value_of_robustness_min_pct": round(rob["vor_min"], 0),
            "value_of_robustness_median_pct": round(rob["vor_median"], 0),
            "value_of_robustness_max_pct": round(rob["vor_max"], 0),
            "n_combinations": int(rob["vor_pct"].size)},
        "validation": {
            "metrics_within_published_range": f"{int(val['within_range'].sum())}/{len(val)}",
            "all_pass": bool(val["within_range"].all())},
        "recommended_performance_high_scenario": {
            "service_level_pct": round(sim["service_level"] * 100, 1),
            "solar_fraction_pct": round(sim["solar_fraction"] * 100, 1),
            "grid_import_kwh": round(sim["grid_import_kwh"], 0)},
        "emissions": {k: round(v, 2) for k, v in emis.items()},
    }


def _write_summary(r: dict):
    rec = r["recommended_design"]
    vor = r["value_of_robustness"]
    lines = [
        "EXECUTIVE SUMMARY",
        "Robust Charging Infrastructure Design Under Demand Uncertainty",
        f"Site: {r['site']} | Constrained grid connection: {r['grid_connection_kW']} kW",
        "=" * 72, "",
        "RECOMMENDED ROBUST STATION SPECIFICATION",
        f"  Solar PV array     : {rec['pv_kwp']} kWp",
        f"  Battery storage    : {rec['battery_kwh']} kWh",
        f"  Charge points      : {rec['n_chargers']} units",
        f"  Capital cost       : GBP {r['recommended_capex_gbp']:,.0f}",
        "",
        "WHY ROBUST DESIGN MATTERS (value of robustness)",
        f"  vs a naive average-demand design, the robust design cuts worst-case",
        f"  annual cost by GBP {vor['worst_cost_reduction']:,.0f}/yr "
        f"({vor['worst_cost_reduction_pct']:.1f}%) and lifts guaranteed fleet",
        f"  service from {vor['naive_min_service']*100:.1f}% to "
        f"{vor['robust_min_service']*100:.1f}% under the worst demand scenario.",
        "",
        "SUSTAINABILITY (recommended design, high-demand scenario)",
        f"  Solar fraction     : {r['recommended_performance_high_scenario']['solar_fraction_pct']}%",
        f"  Carbon saving      : {r['emissions']['carbon_saving_tCO2_yr']} tCO2/yr "
        f"({r['emissions']['carbon_saving_pct']:.0f}% vs grid-only)",
        "",
        "KEY UNCERTAINTY DRIVERS (tornado, ranked)",
    ]
    for s in r["top_sensitivities"]:
        lines.append(f"  - {s['variable']}: swing GBP {s['swing']:,.0f}/yr")
    (config.OUTPUT_DIR / "executive_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_report(figs: dict, r: dict):
    rec = r["recommended_design"]
    vor = r["value_of_robustness"]
    order = ["01_scenario_demand", "04_demand_fan", "02_pareto", "03_design_comparison",
             "05_cost_distribution", "10_robustness", "06_tornado", "09_global_sensitivity",
             "11_validation", "07_energy_balance", "08_energy_sources"]
    titles = {
        "01_scenario_demand": "1. Demand scenarios (from real DfT Newcastle data)",
        "04_demand_fan": "2. Monte-Carlo demand fan (500 samples)",
        "02_pareto": "3. Cost vs robustness — Pareto frontier (5 decision rules)",
        "03_design_comparison": "4. Decision-rule comparison",
        "05_cost_distribution": "5. Cost distribution: naive vs robust",
        "10_robustness": "6. Robustness of the conclusion (penalty x grid sweep)",
        "06_tornado": "7. Tornado sensitivity (one-at-a-time)",
        "09_global_sensitivity": "8. Global sensitivity — total-effect Sobol indices",
        "11_validation": "9. Validation vs published benchmarks",
        "07_energy_balance": "10. Hourly dispatch & battery profile (Theme 2)",
        "08_energy_sources": "11. Energy mix & carbon savings (Theme 3)",
    }
    cards = "".join(
        f'<section><h2>{titles[k]}</h2>'
        f'<iframe src="{figs[k]}" loading="lazy"></iframe></section>'
        for k in order if k in figs)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robust e-Micromobility Charging Station — Results</title>
<style>
 :root{{--g:#43AA8B;--d:#1B1B3A;--a:#2E86AB;}}
 *{{box-sizing:border-box}}
 body{{margin:0;font-family:Arial,Helvetica,sans-serif;color:#222;background:#f4f6f8}}
 header{{background:linear-gradient(120deg,#1B1B3A,#2E86AB);color:#fff;padding:38px 28px}}
 header h1{{margin:0 0 6px;font-size:26px}}
 header p{{margin:2px 0;opacity:.92}}
 .wrap{{max-width:1180px;margin:0 auto;padding:24px}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:24px 0}}
 .kpi{{background:#fff;border-radius:14px;padding:18px 20px;box-shadow:0 2px 10px rgba(0,0,0,.06);border-left:5px solid var(--g)}}
 .kpi b{{display:block;font-size:26px;color:var(--d)}}
 .kpi span{{color:#667;font-size:13px}}
 section{{background:#fff;border-radius:14px;padding:18px 20px;margin:20px 0;box-shadow:0 2px 10px rgba(0,0,0,.06)}}
 section h2{{margin:.2em 0 .6em;color:var(--d);font-size:18px}}
 iframe{{width:100%;height:560px;border:0;border-radius:8px}}
 footer{{text-align:center;color:#889;padding:30px;font-size:13px}}
 .badge{{display:inline-block;background:var(--g);color:#fff;border-radius:20px;padding:3px 12px;font-size:12px;margin-right:6px}}
</style></head><body>
<header>
 <h1>Robust Charging Infrastructure Design Under Demand Uncertainty</h1>
 <p>Solar-powered shared e-micromobility charging station &middot; {r['site']}</p>
 <p><span class="badge">Theme 3 primary</span><span class="badge">Theme 2 secondary</span>
    Newcastle University &middot; Sustainable e-Micromobility Competition 2025-26</p>
</header>
<div class="wrap">
 <div class="kpis">
  <div class="kpi"><span>Recommended robust design</span>
    <b>{rec['pv_kwp']} kWp</b><span>PV &middot; {rec['battery_kwh']} kWh battery &middot; {rec['n_chargers']} chargers</span></div>
  <div class="kpi"><span>Value of robustness (worst-case cost)</span>
    <b>-{vor['worst_cost_reduction_pct']:.0f}%</b><span>GBP {vor['worst_cost_reduction']:,.0f}/yr saved vs naive design</span></div>
  <div class="kpi"><span>Guaranteed fleet service (worst case)</span>
    <b>{vor['robust_min_service']*100:.0f}%</b><span>vs {vor['naive_min_service']*100:.0f}% for the naive design</span></div>
  <div class="kpi"><span>Carbon saving</span>
    <b>{r['emissions']['carbon_saving_tCO2_yr']:.1f} t/yr</b><span>{r['emissions']['carbon_saving_pct']:.0f}% vs grid-only charging</span></div>
 </div>
 {cards}
</div>
<footer>Generated automatically by <code>run_analysis.py</code>.
 Data: DfT e-scooter trials (real), PVGIS-calibrated solar, National Grid ESO carbon intensity.</footer>
</body></html>"""
    (config.OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
