# Final-Round Script - Part A (3-min oral) + Part B (3-min prototype demo)

*Part A is ~434 words = 2.9 min at a calm 150 wpm - keep it under 3:00. Part B is driven from the website's Presenter mode (open the site, press **P** or click **Start 3-minute demo**; arrow keys advance; the built-in timer turns red past 3:00). Total spoken time stays under 6 minutes.*

## PART A - ORAL (3:00, slides 1-6)

### Slide 1 - Problem  (~26s)

Good morning. Instead of asking how large a charger should be for average demand, our prototype asks what design still works when demand, grid limits and future growth change. A hub sized for the average strands bikes on busy days; an oversized one wastes capital. We answer this with robust optimisation on open data - and in three minutes you will see it run live.

### Slide 2 - Method / pipeline  (~32s)

The method in one breath. Demand is calibrated to the UoW Bikes use case from open shared-micromobility evidence; solar comes from PVGIS for Coventry and grid carbon from National Grid ESO. Every candidate hub is simulated over all eight thousand seven hundred and sixty hours of a year. One hundred and fifty designs are scored across fifteen futures under five decision rules - and we recommend the one that still performs well when the future is worse than expected.

### Slide 3 - Final design result  (~34s)

The recommended design is 15 kilowatt-peak of solar, zero kilowatt-hours of battery, and 8 smart-managed bays. Twenty-nine thousand four hundred pounds of capital, twenty-five pence per kilowatt-hour delivered, and three point seven tonnes of CO2 avoided each year. The reason there is no battery: a returned bike only needs to be ready by morning, so smart charging schedules the energy into sunny and off-peak hours and the load never breaks the fifteen-kilowatt connection.

### Slide 4 - Robustness under uncertainty  (~30s)

What does robustness buy? The average-demand design looks cheapest on a normal day, but in the worst demand future its cost reaches forty-seven thousand pounds a year and it strands one bike in twenty-one. The robust design cuts that worst case by nearly sixty percent and lifts guaranteed service from ninety-five point three to ninety-nine point six percent. And we stress-tested the conclusion itself: it held in one hundred percent of thirty-five assumption combinations.

### Slide 5 - Battery threshold & sustainability  (~32s)

This result is not anti-battery. It shows that for a connected Warwick campus hub, smart charging gives the required robustness without extra battery cost, degradation or material impact. We swept the grid connection to find exactly where that changes: at roughly eight to ten kilowatts, storage starts entering the optimal design - and there we specify LFP chemistry with second-life reuse. The most sustainable battery is sometimes the one you do not need to install.

### Slide 6 - Demo handoff + conclusion  (~24s)

That is the argument - now the prototype makes it live: the full model runs in the browser, checks itself against our Python pipeline, and works offline. Watch four things: the recommendation recomputed in front of you; the average-demand design failing where the robust one holds; a battery entering the design when the grid weakens to eight kilowatts; and the validation behind every number. Over to the demo.

## PART B - LIVE PROTOTYPE DEMO (3:00, website Presenter mode, 7 steps)

*Each step scrolls the page and fires its action automatically; speak one line per step.*

| Step | ~t | On screen | Say |
|---|----|-----------|-----|
| 1/7 | 0:00 | Problem section | Shared e-bike demand is uncertain - the average-demand hub is cheap but fragile; the oversized one is reliable but wasteful. |
| 2/7 | 0:25 | Method pipeline | Open solar, carbon and mobility data feed an 8,760-hour simulation - 150 designs, 15 futures, five decision rules. |
| 3/7 | 0:50 | Live model - robust preset | The recommendation: 15 kWp solar, no battery, 8 smart bays - 19,232 pounds worst-case, 99.6% service. Green status: it holds in every future. |
| 4/7 | 1:15 | Live model - naive preset | Every number recomputes live. The average-demand design: watch the status turn amber - cheap on paper, fragile at peaks. |
| 5/7 | 1:40 | Battery threshold | Now weaken the grid to 8 kilowatts - the optimiser adds a battery, live. Storage pays only when the connection is weak, around 8 to 10 kW. |
| 6/7 | 2:15 | Validation | Nine of nine checks in published ranges, the browser matches the Python pipeline to a hundredth of a percent, and one command reproduces everything. |
| 7/7 | 2:40 | Hero / recommendation | The prototype turns uncertain e-bike demand into a clear infrastructure decision: how much solar, whether a battery is needed, and how many smart bays to install. Thank you. |

**Q&A (4:00):** leave the site's validation section or Slide 6 on screen.

**Fallbacks:** no internet -> open `demo.html` from the cloned repo (fully offline). Display failure -> the QR on Slide 6 opens the same demo on any phone.
