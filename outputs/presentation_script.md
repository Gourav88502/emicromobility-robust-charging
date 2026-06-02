# 3-Minute Presentation Script (anonymised)

*Total ~477 words ≈ 3.2 min at a calm 150 wpm. No personal or organisation details — safe for blind Level-1 review.*

## Slide 1 — Title & hook  (~25s)

Charging infrastructure for shared e-scooters hides a trap. Build a solar charging station for average demand, and it collapses when demand peaks. Build it for the worst case, and you sink capital into equipment that mostly sits idle. Our project asks the sharper question: which station should you actually build when the future is uncertain? We answer it with robust optimisation, grounded in real data.

## Slide 2 — The problem  (~30s)

Our hub is a depot charging a mixed fleet of e-scooters, e-bikes and e-cargo bikes, whose demand swings with season, weather and growth. The challenge intensifies because the site has a constrained grid connection — a bigger import limit needs a costly network reinforcement — so the evening charging peak must come from on-site solar and storage. We built Low, Medium and High demand scenarios directly from the real DfT Newcastle e-scooter trial: real trips, fleet size, deployment and trip distance. The demand range is observed, not assumed.

## Slide 3 — Approach  (~30s)

The pipeline is fully reproducible. From the real data we build fifteen demand scenarios, then simulate an eight-thousand-seven-hundred-and-sixty-hour energy balance for every candidate station — solar, to battery, to a capped grid. We evaluate a hundred and fifty designs under five decision rules: naive, a two-stage stochastic program, CVaR, minimax-regret and maximin — then confirm the conclusion holds across every assumption and validate against published benchmarks.

## Slide 4 — Key result  (~35s)

Here is the headline. The naive, average-demand design is cheapest on a normal day, but in the worst demand future it strands about thirteen percent of the fleet and its cost balloons. The robust design eliminates that risk. It cuts worst-case annual cost by more than half and lifts guaranteed fleet service from eighty-seven to ninety-seven percent. The Pareto frontier makes the trade-off explicit: a small expected-cost premium buys large protection against the demand tail.

## Slide 5 — Recommended design  (~25s)

Here is the key insight. Because depot charging is flexible, a smart controller schedules it into sunny, cheap off-peak hours and flattens the overnight load below the connection limit. The consequence is striking: at a grid-connected depot a battery does not pay — the cost-optimal robust design is solar plus enough smart-managed bays. Storage becomes essential only as the connection weakens toward off-grid. Managing the charge profile is the cheapest robustness lever of all — that is Theme two.

## Slide 6 — Feasibility & sustainability  (~25s)

The design is feasible today: off-the-shelf solar, lithium-ion storage and standard low-power charge bays. It cuts operational carbon by about two thirds versus grid-only charging, and all seven key outputs sit within published benchmark ranges. Every number is reproducible — open-source, deterministic, one command, with automated tests — so any reviewer can audit the result.

## Slide 7 — Originality & close  (~15s)

Every line of code and every figure is original, built from scratch, and all three datasets are real — DfT, PVGIS and the National Grid carbon API. In one sentence: we turn demand uncertainty from a risk into a design input — and show that robustness pays. Thank you.
