# Final-Round Script - 3 min oral + 3 min live demo

*Oral half ~485 words = 3.2 min at a calm 150 wpm; keep total oral under 3:00. Demo half is driven from the website's Presenter mode (open the site, press P; arrow keys advance).*

## PART 1 - ORAL (3:00, slides 1-6)

### Slide 1 - Title & hook  (~22s)

Good morning. Charging infrastructure for shared e-bikes hides a trap: size a solar hub for average demand and it strands the fleet at peaks; size it for the worst case and capital sits idle. We asked the sharper question - which hub do you build when the future is uncertain? - and answered it with robust optimisation on real data. In three minutes you will see the model itself run live.

### Slide 2 - The case (10%)  (~32s)

The case: UoW Bikes charges a mixed fleet at a campus depot behind a fifteen-kilowatt grid connection - upgrading that wire means a slow, expensive network reinforcement, so peaks must be met on site. Demand swings with term-time, weather and growth; our Low, Medium and High scenarios are built from real DfT monitoring data, so the demand range is observed, not assumed. The decision is set today - solar, battery, bays - but must perform for years.

### Slide 3 - Approach (10%)  (~30s)

The approach in one breath: real solar from PVGIS, real carbon from National Grid, real demand from DfT. Fifteen probability-weighted futures. For every candidate hub we simulate all eight thousand seven hundred and sixty hours of the year - solar first, then battery, then the capped grid. A hundred and fifty designs are scored under five decision rules, from naive to maximin, and the winner is stress-tested until the conclusion itself proves robust.

### Slide 4 - Result + feasibility (10%)  (~42s)

The result. The naive hub is cheapest on an average day but collapses in the high-demand future: forty-seven thousand pounds a year and one bike in twenty-one stranded. The robust hub - fifteen kilowatt-peak of solar and eight smart-managed bays - cuts that worst case by fifty-nine percent and guarantees ninety-nine point six percent service. And the surprise: no battery. Smart charging flattens the load below the grid limit, so at a connected site storage adds cost and embodied carbon for nothing. Everything is off-the-shelf hardware, validated nine-for-nine against published benchmarks.

### Slide 5 - Scalability, Safety & Cost (10%)  (~32s)

Scaling, safety, cost. A city scales by copying twenty-nine-thousand-pound modular hubs - no grid reinforcement - and under the UK-India partnership the same pipeline re-sizes for Indian solar and two- and three-wheeler fleets. Safety is standards-mapped: LFP chemistry where storage is used, BS EN battery standards, IP65 bays, and the peak is enforced in software and hardware. Costs are end-to-end: twenty-five pence per kilowatt-hour delivered, and three point seven tonnes of CO2 avoided every year, stated honestly on a marginal basis.

### Slide 6 - Demo handoff (into the 40%)  (~22s)

That is the argument - now watch the model make it. The demonstration you are about to see is not a video and not slides: the full dispatch engine runs live in the browser, validated against our Python pipeline at load time. Four things to watch: the hub animated hour by hour; the naive design failing where the robust one holds; the browser re-searching all one hundred and fifty designs in about a second; and a battery entering the design the moment the grid weakens to eight kilowatts. Over to the demo.

## PART 2 - LIVE DEMO (3:00, website Presenter mode)

*Open docs/index.html (or the GitHub Pages URL), press **P**. The overlay*
*shows each cue and a running timer; -> advances. Steps 1-10 below match*
*the on-screen tour. Speak over each step; the actions fire automatically.*

| # | ~t | On screen | Say |
|---|----|-----------|-----|
| 1 | 0:00 | Hub animation playing | This is the hub - every flow is the real model's hourly output, not an illustration. |
| 2 | 0:20 | The case section | Sized for average, it fails; sized for the worst, it wastes. Robust design threads that needle. |
| 3 | 0:40 | Approach pipeline | Real DfT, PVGIS and National Grid data; 15 futures; 8,760-hour physics; 5 decision rules. |
| 4 | 1:00 | Lab - naive preset | The naive hub: watch the worst-case cost and the service KPI go red. |
| 5 | 1:25 | Lab - robust preset | The robust hub: minus 59% worst-case, 99.6% guaranteed. That's the value of robustness. |
| 6 | 1:50 | Click Optimise | The browser is now re-solving all 150 designs across 15 futures - 20 million hours - done in a second. Five rules, same winner. |
| 7 | 2:20 | Grid slider to 8 kW | Weaken the grid and the optimiser buys a battery - the storage boundary is nine kilowatts. That's a design rule, not a guess. |
| 8 | 2:40 | Theme 2 profiles | Physics per route: 4 to 18 watt-hours per km. Shared bikes cycle 1.3x harder - hence the managed hub. |
| 9 | 2:50 | Scale-Safety-Cost | Modular GBP 29k hubs, LFP + BS EN safety, 25p per kWh delivered - and the same pipeline re-sizes for India. |
| 10 | 2:58 | Validation close | Nine-for-nine validated, fully reproducible - we made uncertainty a design input. Thank you. |

**Q&A (4:00):** leave Slide 7 (backdrop) or the site's validation section on screen.
