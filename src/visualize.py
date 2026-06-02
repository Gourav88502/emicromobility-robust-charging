"""
visualize.py
============
Publication-quality, interactive Plotly figures for every EoI deliverable:

  * scenario demand profiles (Low / Medium / High)
  * Monte-Carlo demand & cost fan (naive vs robust)
  * cost-vs-robustness Pareto frontier with the four design rules
  * tornado sensitivity chart
  * hourly energy-balance dispatch (representative week) — Theme 2
  * design comparison bars (worst-case vs expected cost)
  * energy-source & emissions breakdown

All figures share one clean theme and a colour-blind-friendly palette.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config

# --------------------------------------------------------------------------- #
#  Theme
# --------------------------------------------------------------------------- #
C = {
    "pv": "#F2B705",          # solar gold
    "battery": "#2E86AB",     # storage blue
    "grid": "#A23B72",        # grid magenta
    "demand": "#1B1B3A",      # near-black
    "unmet": "#E03616",       # alert red
    "low": "#43AA8B",         # green
    "medium": "#F8961E",      # amber
    "high": "#E03616",        # red
    "naive": "#E03616",
    "stochastic": "#F8961E",
    "minimax_regret": "#577590",
    "maximin_robust": "#43AA8B",
    "accent": "#43AA8B",
    "muted": "#9AA0A6",
}
FONT = "Arial, Helvetica, sans-serif"
RULE_LABELS = {
    "naive_deterministic": "Naive (deterministic)",
    "stochastic": "Stochastic (chance-constr.)",
    "minimax_regret": "Minimax regret",
    "maximin_robust": "Maximin (robust)",
}


def _layout(fig: go.Figure, title: str, height: int = 460, **kw) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family=FONT, color=C["demand"])),
        font=dict(family=FONT, size=13, color="#222"),
        template="plotly_white", height=height,
        margin=dict(l=70, r=30, t=70, b=60),
        legend=dict(bgcolor="rgba(255,255,255,0.6)", bordercolor="#ddd", borderwidth=1),
        **kw)
    return fig


# --------------------------------------------------------------------------- #
#  1. Scenario demand profiles
# --------------------------------------------------------------------------- #
def fig_scenario_demand(scenario_summary: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    colors = {"Low": C["low"], "Medium": C["medium"], "High": C["high"]}
    for _, r in scenario_summary.iterrows():
        sc = r["scenario"]
        fig.add_trace(go.Bar(
            name=sc, x=["Year 0", f"Year {config.PROJECT_LIFETIME_YEARS}"],
            y=[r["annual_kwh_year0"], r["annual_kwh_final"]],
            marker_color=colors.get(sc, C["muted"]),
            text=[f"{r['annual_kwh_year0']:,.0f}", f"{r['annual_kwh_final']:,.0f}"],
            textposition="outside"))
    fig.update_layout(barmode="group", yaxis_title="Annual charging demand (kWh)")
    return _layout(fig, "Charging-demand scenarios (Low / Medium / High)")


# --------------------------------------------------------------------------- #
#  2. Monte-Carlo demand fan
# --------------------------------------------------------------------------- #
def fig_demand_fan(demand_samples: np.ndarray, n_show: int = 80) -> go.Figure:
    """demand_samples: array [n_samples x 12] monthly demand (kWh)."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    p05 = np.percentile(demand_samples, 5, axis=0)
    p50 = np.percentile(demand_samples, 50, axis=0)
    p95 = np.percentile(demand_samples, 95, axis=0)
    fig = go.Figure()
    idx = np.random.default_rng(0).choice(len(demand_samples),
                                          min(n_show, len(demand_samples)), replace=False)
    for i in idx:
        fig.add_trace(go.Scatter(x=months, y=demand_samples[i], mode="lines",
                                 line=dict(color="rgba(67,170,139,0.10)", width=1),
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=months + months[::-1], y=list(p95) + list(p05[::-1]),
                             fill="toself", fillcolor="rgba(46,134,171,0.18)",
                             line=dict(color="rgba(0,0,0,0)"), name="P5-P95 band"))
    fig.add_trace(go.Scatter(x=months, y=p50, mode="lines+markers",
                             line=dict(color=C["battery"], width=3), name="Median (P50)"))
    fig.update_layout(yaxis_title="Monthly charging demand (kWh)")
    return _layout(fig, f"Monte-Carlo demand fan ({len(demand_samples)} samples)")


# --------------------------------------------------------------------------- #
#  3. Monte-Carlo cost distribution (naive vs robust)
# --------------------------------------------------------------------------- #
def fig_cost_distribution(mc_naive: pd.DataFrame, mc_robust: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=mc_naive["annual_cost"], name="Naive design",
                               marker_color=C["naive"], opacity=0.6, nbinsx=40))
    fig.add_trace(go.Histogram(x=mc_robust["annual_cost"], name="Robust design",
                               marker_color=C["maximin_robust"], opacity=0.6, nbinsx=40))
    for d, col, nm in [(mc_naive, C["naive"], "Naive"),
                       (mc_robust, C["maximin_robust"], "Robust")]:
        p95 = d["annual_cost"].quantile(0.95)
        fig.add_vline(x=p95, line=dict(color=col, dash="dash"),
                      annotation_text=f"{nm} P95", annotation_position="top")
    fig.update_layout(barmode="overlay", xaxis_title="Annual cost (GBP/yr)",
                      yaxis_title="Monte-Carlo frequency")
    return _layout(fig, "Annual-cost distribution under uncertainty (500 samples)")


# --------------------------------------------------------------------------- #
#  4. Cost-vs-robustness Pareto frontier
# --------------------------------------------------------------------------- #
def fig_pareto(opt: dict) -> go.Figure:
    designs = opt["_designs"]
    ec = opt["_expected_cost"]
    wc = opt["_worst_cost"]
    feas = opt["_feasible"]
    fig = go.Figure()
    # all designs
    fig.add_trace(go.Scatter(
        x=ec[~feas], y=wc[~feas], mode="markers", name="Design (fails high demand)",
        marker=dict(color=C["muted"], size=6, opacity=0.45,
                    line=dict(width=0)), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=ec[feas], y=wc[feas], mode="markers", name="Design (robustly feasible)",
        marker=dict(color=C["accent"], size=8, opacity=0.7)))
    # frontier line
    pf = opt["pareto"].sort_values("expected_cost")
    fig.add_trace(go.Scatter(x=pf["expected_cost"], y=pf["worst_cost"], mode="lines",
                             line=dict(color=C["demand"], width=2, dash="dot"),
                             name="Pareto frontier"))
    # the four rules
    for rule, info in opt["rules"].items():
        i = info["index"]
        fig.add_trace(go.Scatter(
            x=[ec[i]], y=[wc[i]], mode="markers+text",
            marker=dict(color=C.get(rule, C["demand"]), size=16, symbol="star",
                        line=dict(width=1.5, color="white")),
            text=[RULE_LABELS[rule]], textposition="top center",
            textfont=dict(size=11, color=C.get(rule, C["demand"])),
            name=RULE_LABELS[rule]))
    fig.update_layout(xaxis_title="Expected annual cost (GBP/yr)",
                      yaxis_title="Worst-case annual cost (GBP/yr)")
    return _layout(fig, "Cost vs robustness — Pareto frontier & decision rules", height=560)


# --------------------------------------------------------------------------- #
#  5. Tornado sensitivity
# --------------------------------------------------------------------------- #
def fig_tornado(tornado_df: pd.DataFrame, output_label: str = "Annual cost (GBP/yr)") -> go.Figure:
    t = tornado_df.iloc[::-1]                    # largest swing at top
    base = t["baseline_output"].iloc[0]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=t["variable"], x=t["low_output"] - base, base=base, orientation="h",
        marker_color=C["low"], name="Low input",
        hovertemplate="%{y}<br>Low: %{base:.0f}+(%{x:.0f})<extra></extra>"))
    fig.add_trace(go.Bar(
        y=t["variable"], x=t["high_output"] - base, base=base, orientation="h",
        marker_color=C["high"], name="High input",
        hovertemplate="%{y}<br>High<extra></extra>"))
    fig.add_vline(x=base, line=dict(color=C["demand"], width=2),
                  annotation_text="Baseline", annotation_position="top")
    fig.update_layout(barmode="overlay", xaxis_title=output_label,
                      yaxis_title="", bargap=0.35)
    return _layout(fig, "Tornado sensitivity — drivers of cost for the robust design")


# --------------------------------------------------------------------------- #
#  5b. Global (variance-based) sensitivity — total-effect Sobol indices
# --------------------------------------------------------------------------- #
def fig_global_sensitivity(sobol_df: pd.DataFrame) -> go.Figure:
    d = sobol_df.sort_values("total_order")          # ascending -> largest on top
    colors = [C["accent"] if v >= d["pct_total"].max() - 1e-9 else C["battery"]
              for v in d["pct_total"]]
    fig = go.Figure(go.Bar(
        y=d["variable"], x=d["pct_total"], orientation="h",
        marker_color=colors, text=[f"{v:.0f}%" for v in d["pct_total"]],
        textposition="outside",
        hovertemplate="%{y}<br>total-effect: %{x:.1f}% of cost variance<extra></extra>"))
    fig.update_layout(xaxis_title="Total-effect Sobol index — share of annual-cost variance (%)",
                      yaxis_title="", xaxis_range=[0, max(50, d['pct_total'].max() * 1.18)])
    return _layout(fig, "Global sensitivity — total-effect Sobol indices (incl. interactions)")


# --------------------------------------------------------------------------- #
#  6. Hourly energy-balance dispatch (representative week) — Theme 2
# --------------------------------------------------------------------------- #
def fig_energy_balance(sim_result: dict, start_hour: int = 4320, hours: int = 168) -> go.Figure:
    """Stacked dispatch + battery SoC for a representative week (default: July)."""
    s = slice(start_hour, start_hour + hours)
    t = np.arange(hours)
    pv_d = sim_result["_pv_to_demand"][s]
    bat_d = sim_result["_batt_to_demand"][s]
    grid = sim_result["_grid_import"][s]
    unmet = sim_result["_unmet"][s]
    soc = sim_result["_soc"][s]
    soc_pct = soc / max(sim_result["design"].battery_kwh * config.BATTERY_DOD, 1e-9) * 100

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=t, y=pv_d, stackgroup="s", name="PV -> demand",
                             line=dict(width=0.5, color=C["pv"]), fillcolor=C["pv"]))
    fig.add_trace(go.Scatter(x=t, y=bat_d, stackgroup="s", name="Battery -> demand",
                             line=dict(width=0.5, color=C["battery"]), fillcolor=C["battery"]))
    fig.add_trace(go.Scatter(x=t, y=grid, stackgroup="s", name="Grid -> demand",
                             line=dict(width=0.5, color=C["grid"]), fillcolor=C["grid"]))
    if unmet.sum() > 0:
        fig.add_trace(go.Scatter(x=t, y=unmet, stackgroup="s", name="Unmet demand",
                                 line=dict(width=0.5, color=C["unmet"]), fillcolor=C["unmet"]))
    fig.add_trace(go.Scatter(x=t, y=soc_pct, name="Battery SoC (%)",
                             line=dict(color=C["demand"], width=2, dash="dot")),
                  secondary_y=True)
    fig.update_xaxes(title_text="Hour of representative week")
    fig.update_yaxes(title_text="Power delivered (kWh/h)", secondary_y=False)
    fig.update_yaxes(title_text="Battery state of charge (%)", range=[0, 105],
                     secondary_y=True)
    return _layout(fig, "Hourly energy-balance dispatch & battery profile (Theme 2)",
                   height=480)


# --------------------------------------------------------------------------- #
#  7. Design comparison (four rules)
# --------------------------------------------------------------------------- #
def fig_design_comparison(opt: dict) -> go.Figure:
    rules = list(opt["rules"].keys())
    labels = [RULE_LABELS[r] for r in rules]
    expected = [opt["rules"][r]["expected_cost"] for r in rules]
    worst = [opt["rules"][r]["worst_cost"] for r in rules]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=expected, name="Expected cost",
                         marker_color=C["battery"],
                         text=[f"£{v:,.0f}" for v in expected], textposition="outside"))
    fig.add_trace(go.Bar(x=labels, y=worst, name="Worst-case cost",
                         marker_color=C["high"],
                         text=[f"£{v:,.0f}" for v in worst], textposition="outside"))
    fig.update_layout(barmode="group", yaxis_title="Annual cost (GBP/yr)")
    return _layout(fig, "Design rule comparison — expected vs worst-case cost")


# --------------------------------------------------------------------------- #
#  8. Energy source & emissions
# --------------------------------------------------------------------------- #
def fig_energy_sources(sim_result: dict, emis: dict) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "xy"}]],
                        subplot_titles=("Energy supplied to demand",
                                        "Annual CO2: station vs grid-only"))
    pv = sim_result["pv_to_demand_kwh"]
    bat = sim_result["battery_to_demand_kwh"]
    grid = sim_result["grid_to_demand_kwh"]
    fig.add_trace(go.Pie(labels=["PV direct", "Battery", "Grid"], values=[pv, bat, grid],
                         marker=dict(colors=[C["pv"], C["battery"], C["grid"]]),
                         hole=0.45, textinfo="percent"), row=1, col=1)
    fig.add_trace(go.Bar(
        x=["Grid-only", "Solar station"],
        y=[emis["counterfactual_emissions_tCO2_yr"], emis["station_emissions_tCO2_yr"]],
        marker_color=[C["grid"], C["maximin_robust"]],
        text=[f"{emis['counterfactual_emissions_tCO2_yr']:.1f} t",
              f"{emis['station_emissions_tCO2_yr']:.1f} t"],
        textposition="outside", showlegend=False), row=1, col=2)
    fig.update_yaxes(title_text="tCO2 / yr", row=1, col=2)
    return _layout(fig, "Energy mix & carbon savings (Theme 3 sustainability)", height=440)


if __name__ == "__main__":
    print("visualize.py — import and call the fig_* functions from run_analysis.py")
