# 3-Minute Presentation Script (anonymised)

*Total ~451 words ≈ 3.0 min at a calm 150 wpm. No personal or organisation details — safe for blind Level-1 review.*

## Slide 1 — Title & hook  (~25s)

Charging infrastructure for shared e-bikes hides a trap. Size a solar station for average demand and it collapses at peaks; size it for the worst case and capital sits idle. Our project asks the sharper question: which station do you build when the future is uncertain? We answer it with robust optimisation, grounded in real data.

## Slide 2 — The problem  (~30s)

Our hub is a depot charging a mixed fleet whose demand swings with season, weather and growth, behind a constrained grid connection — a bigger import limit needs a costly network reinforcement, so the evening peak must come from on-site solar and storage. We built Low, Medium and High scenarios directly from the real UoW Bikes shared e-bike trial: real trips, fleet size, deployment and distance. The demand range is observed, not assumed.

## Slide 3 — Approach  (~30s)

The pipeline is fully reproducible. From fifteen demand scenarios we run an eight-thousand-seven-hundred-and-sixty-hour energy balance for every candidate hub: solar, to battery, to a capped grid. We score a hundred and fifty designs under five decision rules — naive, two-stage stochastic, CVaR, minimax-regret and maximin — then confirm the result holds across every assumption and validate it against published benchmarks.

## Slide 4 — Key result  (~35s)

Here is the headline. The naive design is cheapest on a normal day, but in the worst demand future it strands roughly one bike in sixteen and its cost balloons. The robust design cuts worst-case annual cost by over sixty percent and lifts guaranteed fleet service from about ninety-four to over ninety-nine percent, a small expected-cost premium buying large protection against the demand tail.

## Slide 5 — Recommended design  (~25s)

Theme two looks at how the batteries are used. A physics model gives the energy per ride from gradient, speed and load: about four watt-hours per kilometre on a flat hop, eighteen on a hilly cargo run. The profiles then split. A private bike takes one deep overnight charge at home; a shared bike drains deeper over many trips and tops up at the depot. Shared batteries work a third harder and age faster, so a shared scheme needs the managed hub, and smart charging keeps a battery off the bill unless the grid is weak.

## Slide 6 — Feasibility & sustainability  (~25s)

The design is feasible today: off-the-shelf solar, lithium-ion storage and standard low-power charge bays. It cuts operational carbon by about 15 percent versus grid-only charging, and all seven key outputs sit within published benchmark ranges. Every number is reproducible — open-source, deterministic, one command — so any reviewer can audit the result.

## Slide 7 — Originality & close  (~15s)

Every line of code and every figure is original, built from scratch. Solar and grid carbon are real API data; demand is modelled from published shared-bike statistics and validated. In one sentence: we turn demand uncertainty from a risk into a design input, and show that robustness pays. Thank you.
