# Defense Notes — how to explain & defend this project

> Private prep for the team. The judges score the in‑person **demonstration (40%)**
> and **presentation clarity (20%)**, and the Level‑1 round runs an **AI/originality
> check**. The single best thing you can do is be able to explain every part in your
> own words. Read this, run the model once yourself, and rehearse the answers.

---

## 1. The project in 4 sentences (say it like this)
A shared e‑bike scheme needs a place to charge its fleet from solar. The hard part
is **sizing** it: build for average demand and you strand bikes on busy days; build
for the worst case and you waste money. We use **robust optimisation** to pick the
solar + battery + charge‑bay design that performs across *every* plausible future
demand, and we quantify what that robustness is worth. The answer for a
grid‑connected hub at the University of Warwick is **15 kWp of solar, no battery,
8 smart‑managed bays**.

## 2. Numbers to memorise
- Recommended design: **15 kWp PV · 0 kWh battery · 8 smart bays**, CAPEX **≈ £29,400**.
- Value of robustness: worst‑case annual cost **−62%** (£56,994 → **£21,472/yr**); guaranteed service **94.1% → 99.4%**.
- Holds in **100% of 35** penalty×grid stress tests; **9/9** outputs validated.
- Carbon: avoids **3.8 tCO₂/yr (~15%** of grid‑only, marginal basis); **15%** solar fraction.
- Battery only enters the design at a weak grid (**≤ ~8–10 kW**); at 15 kW smart charging beats it.
- Theme 2: route energy **4–18 Wh/km**; shared bikes cycle **~1.3×** more than private bikes.

## 3. How each piece works (plain English)
- **Demand scenarios** — Low/Med/High usage × 5 growth rates = 15 weighted futures. Built in `src/demand_model.py`.
- **Route energy model (Theme 2, `src/route_energy.py`)** — Newton's laws: force = rolling + gradient + air drag (+ stop‑go); energy/km = force × distance ÷ drivetrain efficiency × motor‑assist share. Gives 4–18 Wh/km by route.
- **Hourly energy balance (`src/energy_balance.py`)** — for all 8,760 hours of the year: send solar to demand first, then battery, then the capped grid; anything left is "unmet" and priced as lost service.
- **Optimisation (`src/optimization.py`)** — score all 150 designs (PV×battery×bays) over the 15 scenarios, then pick with **5 rules**: naive, two‑stage stochastic, CVaR, minimax‑regret, **maximin** (our pick).
- **Stress tests** — Monte‑Carlo (500 runs), Sobol sensitivity, and a penalty×grid×horizon sweep to prove the answer isn't an artefact of one assumption.
- **Validation (`src/validation.py`)** — 9 outputs *and inputs* checked against published ranges.

## 4. Tough questions — and honest answers
**"Is this AI‑generated / is it really your work?"**
> The model, the optimisation and the route physics are ours; we used AI as a coding
> assistant the way we'd use Stack Overflow or a library. We can derive the energy
> equation, explain each decision rule, and reproduce every number live — *(then do it)*.

**"Your demand data is synthetic, not the real UoW data."**
> Correct, and we're upfront about it. Demand is a **representative series calibrated
> to published shared‑e‑bike usage** (trips/bike/day and trip distance are *validated*
> against literature — see the validation table). The loader **auto‑ingests the official
> `UoW Bikes Data(Sheet1).csv`** the moment it's available, with no code change. Solar
> and grid‑carbon are **real** API data (PVGIS, National Grid ESO).

**"Isn't the naive baseline a strawman?"**
> The naive design is the standard deterministic approach (size to the forecast). But we
> don't only beat that: the same search also produced **stochastic and CVaR** designs, and
> our maximin design still gives the **lowest worst‑case cost** of all of them.

**"Why the marginal carbon factor — doesn't that inflate savings?"**
> We report on a **consequential (marginal) basis** because on‑site solar displaces the
> *marginal* plant (gas). It gives a modest **~15%** — we're not cherry‑picking; we state
> the basis explicitly and the average‑grid figure is in the data.

**"You recommend *no* battery in a sustainability competition?"**
> Yes — that *is* the sustainable answer here. Smart charging already flattens the load
> under the grid limit, so a battery would add cost **and embodied carbon** for no benefit.
> Our grid sweep shows storage only pays at a weak ≤8–10 kW connection; there we spec a
> long‑life, cobalt/nickel‑free **LFP** pack with second‑life and ~45% material recovery.

**"What exactly did you do for Theme 2?"**
> A physics route model for energy per km, and a 24‑hour charge/discharge comparison of a
> **private** vs a **shared** e‑bike. Private = one deep overnight home charge; shared =
> many shallow trips + depot charging, ~1.3× more cycling. That's why shared fleets need
> the managed hub. *(Point to Figure 3.)*

## 5. Live demo script (have this ready)
1. `python run_analysis.py` → show it rebuild data, model and figures in under a minute.
2. Open `outputs/index.html` → walk the Pareto frontier (cost vs robustness).
3. `streamlit run dashboard/app.py` → drag the **grid‑limit** slider down past ~10 kW and show the battery becoming worthwhile (the storage boundary, live).
4. Show `python -m pytest -q` passing → "every number is reproducible."

## 6. Before you submit (your checklist)
- [ ] Get the real `UoW Bikes Data(Sheet1).csv`, drop in `data/raw/`, re‑run. (Biggest score lever.)
- [ ] Confirm eligibility — the competition is for **UK HEI** teams.
- [ ] Export the **PDF from the .docx in Word** (locks the Aptos font); keep both anonymous.
- [ ] Record the ≤3‑min video from `outputs/presentation_script.md` (no name/face/logo).
- [ ] Set your real team alias in `scripts/build_executive_summary.py` and re‑run.
- [ ] Be able to run the demo and answer Section 4 without notes.
