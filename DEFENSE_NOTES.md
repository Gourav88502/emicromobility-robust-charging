# Defense Notes — Final Round (in-person, WMG, 6 July 2026)

> Your slot: **3 min oral + 3 min demo + 4 min Q&A**. Weights: Case 10% ·
> Feasibility 10% · Approach 10% · **Demo 40%** · Scalability/Safety/Cost 10% ·
> **Clarity 20%**. The single best thing you can do is be able to explain every
> part in your own words and land the demo inside 3:00. Rehearse with the
> website's Presenter mode (press **P**) — it has a built-in timer.

---

## 1. The project in 4 sentences (say it like this)

A shared e-bike scheme needs a place to charge its fleet from solar. The hard
part is **sizing** it: build for average demand and you strand bikes on busy
days; build for the worst case and you waste money. We use **robust
optimisation** to pick the solar + battery + charge-bay design that performs
across *every* plausible future demand, and we quantify what that robustness
is worth. The answer for a grid-connected hub at the University of Warwick is
**15 kWp of solar, no battery, 8 smart-managed bays**.

## 2. Numbers to memorise (all from `outputs/results.json`)

- Recommended design: **15 kWp PV · 0 kWh battery · 8 smart bays**, CAPEX **£29,400**, LCOE **£0.253/kWh**.
- Value of robustness: worst-case annual cost **−59%** (£47,179 → **£19,232/yr**); guaranteed service **95.3% → 99.6%**; max regret £27,947 → **£1,488**.
- Conclusion holds in **100% of 35** penalty × grid × horizon stress tests; **9/9** outputs & inputs validated.
- Carbon: avoids **3.7 tCO₂/yr** (**15%** vs grid-only, *marginal* basis), **55 t** over the PV lifetime; **15.3%** solar fraction in the high-demand year.
- **Storage boundary ≈ 9 kW**: battery enters the robust design at ≤8 kW grid, gone at ≥10 kW.
- Theme 2: route energy **4–18 Wh/km**; shared bikes cycle **169 vs 127 EFC/yr ≈ 1.3×** harder than private; shared daily minimum SoC 56% vs 65%.
- Live demo engine: matches the Python pipeline to **<0.005%** across reference designs; full 150-design search ≈ **1 s** in-browser.

## 3. The 10-minute slot — runbook

**0:00–3:00 oral** — slides 1–6 (script in `outputs/presentation_script.md`).
One presenter, calm 150 wpm. Slide 6 hands off to the demo.

**3:00–6:00 demo** — open the site, press **P**, arrow keys through the
10 cues (each fires its action automatically: presets, live optimisation,
grid slider). The overlay timer turns red past 3:00 — *wrap up, don't rush*.

**6:00–10:00 Q&A** — leave Slide 7 (backdrop) or the site's validation
section on screen. Split answers across the team; whoever owns a module
answers for it.

**Contingencies (test at lunch with the organisers):**
- Organiser laptop, no internet → open **`demo.html`** from the cloned repo
  (single file, fully offline — everything embedded).
- GitHub Pages works → `https://gourav88502.github.io/emicromobility-robust-charging/`.
- Total display failure → QR code on Slide 6: judges open it on their phones.
- Rehearse once on the actual laptop: keyboard focus must be on the page for
  **P** / arrows to work (click the page background once first).

## 4. How each piece works (plain English)

- **Demand scenarios** — Low/Med/High usage × 5 growth rates = 15 weighted futures at the 5-yr horizon. Built in `src/demand_model.py` from real DfT monitoring data (seasonality, intensity, trip distance), auto-ingesting the official UoW Bikes CSV when present.
- **Route energy model (Theme 2, `src/route_energy.py`)** — Newton's laws: rolling + gradient + air drag; energy/km = force × distance ÷ drivetrain efficiency × motor-assist share → 4–18 Wh/km by route.
- **Hourly energy balance (`src/energy_balance.py`)** — all 8,760 h: PV → demand, surplus → battery → export (capped); deficit → battery → capped grid; remainder = **unmet** (priced as lost service).
- **Optimisation (`src/optimization.py`)** — 150 designs × 15 scenarios scored under **5 rules**: naive, two-stage stochastic, CVaR, minimax-regret, **maximin** (our pick — the only rule judged on the worst case alone).
- **Stress tests** — 500-run Monte-Carlo, Sobol global sensitivity, penalty × grid × horizon sweep (35 combos, 100% hold).
- **Validation (`src/validation.py`)** — 9 outputs *and inputs* inside published ranges; LP dispatch re-verifies the greedy controller on every reported design.
- **The website** — a JavaScript re-implementation of the same dispatch + economics, self-validated against Python reference results at page load. It is **the model**, not a recording of it.

## 5. Tough questions — honest answers

**"Is the browser demo the real model or a toy?"**
> The real one. The page embeds the real PVGIS solar series and the same demand
> construction, re-implements the dispatch and cost equations, and **checks
> itself against the Python pipeline at load** — the badge shows the max
> deviation (<0.005%). Same 150 designs, same 15 scenarios, same five rules,
> same winner: 15/0/8 at £19,232.

**"Why maximin? Isn't it over-conservative?"**
> For infrastructure with a service obligation the binding question is the bad
> year, not the average one. We *show* all five rules — maximin is the only one
> that is fully robustly feasible, and its expected-cost premium over the
> stochastic optimum is small (≈£565/yr) for a £27.9k cut in worst-case cost.

**"Greedy dispatch, not an LP — is the search biased?"**
> We verify it: every reported design is re-evaluated under LP-optimal
> rolling-horizon dispatch (`lp_verification.csv`), and the LP never changes
> the ranking — the standard surrogate-search + exact-verification pattern.

**"You recommend *no* battery in a sustainability competition?"**
> Yes — that *is* the sustainable answer here. Smart charging already flattens
> the load under the 15 kW limit, so a battery adds cost **and embodied
> carbon** for no service gain. The sweep shows exactly where that flips:
> ≤8 kW grid. There we spec a cobalt-free **LFP** pack with second-life reuse —
> see `SAFETY_AND_SCALING.md`.

**"What about safety?"** *(new 10% criterion — own it proactively)*
> Battery-free at this site is the biggest safety decision. Where storage is
> used: LFP chemistry (≈270 °C runaway onset), outdoor IP-rated cabinet with
> 1 m clearance and BMS cut-offs, mapped to BS EN 62485-5 / 50604-1 and
> PAS 7061/7062; bays are 3 kW AC with Type-B RCDs under BS 7671, sheltered,
> ventilated, away from escape routes. The 15 kW peak is enforced in software
> *and* hardware fusing.

**"How does this scale?"**
> By **replication, not reinforcement**: the binding constraint is the grid
> connection, so a city deploys N £29k modular hubs where bikes cluster.
> Re-siting is a data swap (coordinates, demand CSV, grid cap). Under the
> UK–India partnership the same pipeline re-sizes for ~1.6× solar yield and
> 2/3-wheeler packs — and weak Indian feeders fall below the 9 kW boundary,
> where our storage + LFP safety case becomes the design.

**"Where does your demand data come from — is it real?"**
> Built from the **real DfT shared-micromobility monitoring data** (Jan 2022 –
> May 2024, Open Government Licence): real monthly seasonality, usage intensity
> and trip distance, adapted to the UoW scheme and validated against published
> ranges (9/9). Solar is a live PVGIS pull for Coventry; carbon is National
> Grid ESO West Midlands. The loader auto-ingests the official
> `UoW Bikes Data(Sheet1).csv` with no code change.

**"Why marginal carbon accounting?"**
> On-site solar displaces the *marginal* plant (gas), so consequential
> accounting is the honest basis — and we state it. It gives a modest 15%;
> the average-intensity series is in the repo for comparison.

**"Isn't the naive baseline a strawman?"**
> It's the industry default (size to the central forecast). And we don't only
> beat it — stochastic, CVaR and minimax-regret designs from the same search
> are all shown; maximin still has the lowest worst-case cost.

**"Is this AI-generated / really your work?"**
> The model, the optimisation and the route physics are ours; we used AI as a
> coding assistant the way we'd use Stack Overflow. We can derive the energy
> equation, explain each decision rule, and reproduce every number live —
> *(then do it, in the lab)*.

**"Why a 95% service target / £10 per kWh unmet?"**
> 95% is a defensible operator service level; £10/kWh is *conservative* against
> a bottom-up value of lost load (one undelivered kWh ≈ several £3–4 rides).
> The conclusion is insensitive to both — that's what the 35-combination sweep
> is for (100% hold).

**"Growth of 15%/yr for 5 years — really?"**
> That's the *high* branch, weighted accordingly, and long-horizon growth is
> capped by an S-curve saturation (3× year-0) so projections stay physical.

## 6. Before the day (checklist)

- [ ] **Register every team member by Thu 2 Jul, 5 pm** (mandatory — link on the workshop page).
- [ ] If slides changed (they did): **email `outputs/Presentation.pptx` to amruta.joshi@warwick.ac.uk by Fri 3 Jul, 5 pm**. Put team & member names on Slide 1 first (`TEAM_LINE` in `scripts/build_presentation.py`, then re-run it).
- [ ] `git push` everything; confirm the **GitHub Pages demo URL** loads on a phone.
- [ ] **At lunch on the day:** open both the Pages URL *and* `demo.html` (offline) on the organiser's laptop; click the page once, press P, check arrows advance.
- [ ] Rehearse ×3 with the Presenter timer: oral ≤3:00, demo ≤3:00.
- [ ] Everyone can answer Section 5 without notes; agree who owns which module in Q&A.
- [ ] Print one copy of the 2-page Executive Summary per judge (optional but classy).
