# 3-Minute Presentation Script (anonymised)

*Total ~434 words ≈ 2.9 min at a calm 150 wpm. No personal or organisation details — safe for blind Level-1 review.*

## Slide 1 — Title & hook  (~25s)

Charging infrastructure for shared e-scooters hides a trap. Build a solar charging station for average demand, and it collapses when demand peaks. Build it for the worst case, and you sink capital into equipment that mostly sits idle. Our project asks the sharper question: which station should you actually build when the future is uncertain? We answer it with robust optimisation, grounded in real data.

## Slide 2 — The problem  (~30s)

Shared e-scooter charging demand swings with season, weather and growth. The challenge intensifies because our site has a constrained grid connection — upgrading it needs a costly network reinforcement — so the evening charging peak must come from on-site solar and storage. We built Low, Medium and High demand scenarios directly from the national e-scooter trial monitoring dataset: real trips, fleet size, utilisation and trip distance. The demand range is observed, not assumed.

## Slide 3 — Approach  (~30s)

Our pipeline is fully reproducible. From the real data we build nine probability-weighted demand scenarios. We then simulate an eight-thousand-seven-hundred-and-sixty-hour energy balance for every candidate station — solar, to battery, to a capped grid — pricing any unmet demand as lost service. We evaluate a hundred and fifty designs against all nine scenarios, then apply four decision rules: naive, stochastic, minimax-regret and maximin. The whole study runs in twenty-five seconds.

## Slide 4 — Key result  (~35s)

Here is the headline. The naive, average-demand design is cheapest on a normal day, but in the worst demand future it strands thirteen percent of the fleet and its cost triples. The robust design eliminates that risk. It cuts worst-case annual cost by sixty percent and lifts guaranteed fleet service from eighty-seven to ninety-nine percent. The Pareto frontier makes the trade-off explicit: a small expected-cost premium buys enormous protection against the tail.

## Slide 5 — Recommended design  (~25s)

The recommended robust station is twenty-five kilowatt-peak of solar, fifty kilowatt-hours of storage and four charge points. The dispatch profile shows how it works: the battery charges overnight and from midday sun, then discharges through the evening collection peak, shaving demand the constrained grid cannot meet. This directly delivers Theme two — modelling charge and discharge profiles under demand scenarios.

## Slide 6 — Feasibility & sustainability  (~25s)

The design is feasible today: off-the-shelf solar, lithium-ion storage and standard chargers, for about sixty-eight thousand pounds. It also cuts operational carbon by eighty-four percent versus grid-only charging. And every number is reproducible — open-source, deterministic, one command, with automated tests — so any reviewer can audit the result.

## Slide 7 — Originality & close  (~15s)

Every line of code and every figure is original, built from scratch; the only external data is reused under the Open Government Licence. In one sentence: we turn demand uncertainty from a risk into a design input — and show that robustness pays. Thank you.
