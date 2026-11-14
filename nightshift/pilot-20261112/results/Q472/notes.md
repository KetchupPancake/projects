# Q472 - e-means vs tuned Lloyd at small k and n; cost-scaling exponents on synthetic mixtures

Status: **done** | runtime 271.67s | 2026-11-12T23:27:48-06:00 -> 2026-11-12T23:32:19-06:00
Spec: TOP10-TEST-SPECS-DRAFT.md item 9; run brief (scaling-exponent framing). Card: `cards/C-e-means-outperforming-k-means-muse-20261111.md`.

## Method

Synthetic Gaussian-mixture grid (easy separable / hard overlapping families; n in [500, 2000, 8000, 32000, 128000]; k in [4, 8, 16, 32]; 3 seeds). Per cell, plain Lloyd and an e-means-style EMA mini-batch solver start from the same random init; Lloyd's 25-iteration loss is the target. e-means is run at epoch budgets [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]; a k-means++ Lloyd gives a stronger loss reference. Per cell: losses, wall time, epochs/iterations to target, distance evaluations. Cost-to-target is fitted as cost ~ n^b (OLS on log-log) per family and solver, for wall time and distance evaluations; the gap trend is the sign of b_lloyd - b_emeans judged against 2 standard errors. The flip region lists the k/n cells where e-means at 2.5 epochs does or does not beat Lloyd-25 and where it is faster to target.

## Assumptions (the card does not fully specify the method)

- The card does not print the authors' batch-size/decay scaling-law formulas. Batch size b = min(n, max(4k, round(sqrt(n*k)))) and an EMA step size cosine-annealed from 0.5 to a floor of 1/(batches per epoch) are this script's heuristics, fixed for every cell (no per-cell tuning).
- e-means components implemented exactly as the card lists them: EMA count N and sum S per cluster, centroid S/N; cosine-annealed step size to a floor; revival every 5 batches for clusters with N < 0.1*mean(N), by splitting the largest-count donor along 1% of the offset to one of its batch points (split detail not in card); init weight 1e-3 so early batches dominate; finalisation = mean of the points assigned during the last epoch of steps.
- Each e-means epoch budget (0.5..5 epochs) is a separate run with its schedule set for that budget; 'epochs to target' is the smallest budget in that grid whose final loss reaches the target, so it is resolved only to the grid.
- Target = loss of plain Lloyd after 25 iterations (or its fixed point if it converges earlier) from the SAME random init e-means uses. 'Reached' = loss <= target*(1+0.001) for both solvers; the card-claim check uses strict loss <= target at 2.5 epochs (the largest grid budget within the card's 2.6).
- 'Tuned Lloyd' = Lloyd with early stopping at the first iteration within the tolerance of its own 25-iteration loss, empty clusters re-seeded at the worst-served point; a k-means++-seeded Lloyd (25 iters) is reported as a stronger loss reference. Restarts are matched by seeds (3 per cell, same init for Lloyd and e-means).
- Cost = single-threaded numpy wall time of the algorithm steps only (loss evaluations for instrumentation are not timed), and point-centroid distance evaluations (iterations*n*k for Lloyd, epochs*n*k for e-means). Wall-time on CPU numpy at these sizes includes per-batch Python overhead and says nothing about the card's GPU 10-45x figures.
- Pooled exponents divide cost by k and fit log(cost/k) on log n across all k; per-k fits are in result.json.
- Synthetic families: d=32, 16 true Gaussian components, unit noise; easy = centres N(0, 4^2), equal weights; hard = centres N(0, 0.35^2), Dirichlet(2) weights. Cluster count k is swept independently of the true 16.
- Brief and spec differ in framing (brief: n-scaling exponents on synthetic families; spec: small k/n grid and flip region). Both are computed from one grid; the corpus text embedding set the CHECKS note mentions is used in Q471, not here.

## Headline

**easy_separable** (60 cells, e-means target unreached in 0):
- wall time to target: b_lloyd = 1.1029, b_emeans = 0.7234 -> gap widens in e-means' favour (b_lloyd - b_emeans = +0.379, 2SE = 0.105)
- distance evals to target: b_lloyd = 1.0842, b_emeans = 0.8487 -> gap widens in e-means' favour (b_lloyd - b_emeans = +0.236, 2SE = 0.098)

**hard_overlapping** (60 cells, e-means target unreached in 1):
- wall time to target: b_lloyd = 1.0875, b_emeans = 0.7304 -> gap widens in e-means' favour (b_lloyd - b_emeans = +0.357, 2SE = 0.063)
- distance evals to target: b_lloyd = 1.0635, b_emeans = 0.8302 -> gap widens in e-means' favour (b_lloyd - b_emeans = +0.233, 2SE = 0.060)

**Card band check** (card claims e-means below Lloyd-25 loss in 1.4-2.6 epochs):
- e-means reached target (within tol) by 5 epochs in 119/120 runs; by 2.5 epochs in 94; median epochs where reached = 1.5
- e-means@2.5ep strictly below Lloyd-25 in 51/120 runs; below k-means++ Lloyd in 48

**Flip summary by n** (k values where e-means@2.5ep beats Lloyd-25 in a seed majority; median em/L25 loss ratio; median Lloyd/e-means time-to-target, >1 = e-means faster):

- easy_separable n=500: loss advantage at 3/4 k values; em/L25 = 0.8609; time ratio = 0.8
- easy_separable n=2000: loss advantage at 2/4 k values; em/L25 = 0.9999; time ratio = 1.549
- easy_separable n=8000: loss advantage at 3/4 k values; em/L25 = 0.9988; time ratio = 2.288
- easy_separable n=32000: loss advantage at 1/4 k values; em/L25 = 1; time ratio = 4.953
- easy_separable n=128000: loss advantage at 2/4 k values; em/L25 = 0.9996; time ratio = 5.648
- hard_overlapping n=500: loss advantage at 0/4 k values; em/L25 = 1.013; time ratio = 1.635
- hard_overlapping n=2000: loss advantage at 0/4 k values; em/L25 = 1.004; time ratio = 4.585
- hard_overlapping n=8000: loss advantage at 1/4 k values; em/L25 = 1.001; time ratio = 5.262
- hard_overlapping n=32000: loss advantage at 1/4 k values; em/L25 = 1; time ratio = 9.409
- hard_overlapping n=128000: loss advantage at 4/4 k values; em/L25 = 0.9993; time ratio = 14.95

## Per-cell grid (medians over seeds)

| family | n | k | em2.5/L25 | em2.5 beats L25 (seeds) | em epochs->target | Lloyd iters->target | Lloyd s->target | em s->target |
|---|---|---|---|---|---|---|---|---|
| easy_separable | 500 | 4 | 1.009 | 1/3 | 1 (unreached 0) | 3 | 0.000409 | 0.000551 |
| easy_separable | 500 | 8 | 0.959 | 2/3 | 1.5 (unreached 0) | 3 | 0.000565 | 0.000769 |
| easy_separable | 500 | 16 | 0.7628 | 3/3 | 1 (unreached 0) | 2 | 0.000566 | 0.000645 |
| easy_separable | 500 | 32 | 0.6502 | 2/3 | 1.5 (unreached 0) | 2 | 0.00107 | 0.00124 |
| easy_separable | 2000 | 4 | 1 | 1/3 | 1 (unreached 0) | 2 | 0.000686 | 0.0011 |
| easy_separable | 2000 | 8 | 1.005 | 1/3 | 2 (unreached 0) | 2 | 0.00123 | 0.00229 |
| easy_separable | 2000 | 16 | 0.6088 | 2/3 | 0.5 (unreached 0) | 2 | 0.00228 | 0.000922 |
| easy_separable | 2000 | 32 | 0.9995 | 2/3 | 2 (unreached 0) | 6 | 0.0122 | 0.00484 |
| easy_separable | 8000 | 4 | 0.998 | 2/3 | 0.5 (unreached 0) | 2 | 0.00254 | 0.00156 |
| easy_separable | 8000 | 8 | 1.005 | 1/3 | 1 (unreached 0) | 3 | 0.00656 | 0.00365 |
| easy_separable | 8000 | 16 | 0.6633 | 2/3 | 0.5 (unreached 0) | 2 | 0.00798 | 0.00287 |
| easy_separable | 8000 | 32 | 0.9996 | 2/3 | 2 (unreached 0) | 10 | 0.0756 | 0.0173 |
| easy_separable | 32000 | 4 | 1 | 1/3 | 0.5 (unreached 0) | 3 | 0.0171 | 0.00547 |
| easy_separable | 32000 | 8 | 1 | 1/3 | 0.5 (unreached 0) | 3 | 0.0299 | 0.0068 |
| easy_separable | 32000 | 16 | 1 | 0/3 | 0.5 (unreached 0) | 3 | 0.0565 | 0.0103 |
| easy_separable | 32000 | 32 | 0.6205 | 2/3 | 0.5 (unreached 0) | 5 | 0.225 | 0.0191 |
| easy_separable | 128000 | 4 | 1 | 0/3 | 0.5 (unreached 0) | 4 | 0.0967 | 0.0196 |
| easy_separable | 128000 | 8 | 1 | 1/3 | 0.5 (unreached 0) | 2 | 0.0895 | 0.0271 |
| easy_separable | 128000 | 16 | 0.7874 | 3/3 | 0.5 (unreached 0) | 3 | 0.272 | 0.0428 |
| easy_separable | 128000 | 32 | 0.9993 | 3/3 | 1 (unreached 0) | 7 | 1.52 | 0.143 |
| hard_overlapping | 500 | 4 | 1.004 | 0/3 | 3 (unreached 1) | 14 | 0.00167 | 0.00149 |
| hard_overlapping | 500 | 8 | 1.01 | 0/3 | 4 (unreached 0) | 13 | 0.00226 | 0.00171 |
| hard_overlapping | 500 | 16 | 1.015 | 0/3 | 3 (unreached 0) | 14 | 0.004 | 0.00152 |
| hard_overlapping | 500 | 32 | 1.025 | 0/3 | 3 (unreached 0) | 8 | 0.00412 | 0.00211 |
| hard_overlapping | 2000 | 4 | 1.002 | 0/3 | 2.5 (unreached 0) | 16 | 0.00564 | 0.00272 |
| hard_overlapping | 2000 | 8 | 1.002 | 0/3 | 2 (unreached 0) | 20 | 0.0117 | 0.00232 |
| hard_overlapping | 2000 | 16 | 1.007 | 0/3 | 3 (unreached 0) | 18 | 0.0185 | 0.00448 |
| hard_overlapping | 2000 | 32 | 1.006 | 0/3 | 3 (unreached 0) | 18 | 0.036 | 0.00705 |
| hard_overlapping | 8000 | 4 | 0.9961 | 2/3 | 1 (unreached 0) | 15 | 0.0189 | 0.00303 |
| hard_overlapping | 8000 | 8 | 1.001 | 0/3 | 2 (unreached 0) | 16 | 0.0356 | 0.00725 |
| hard_overlapping | 8000 | 16 | 1.001 | 0/3 | 3 (unreached 0) | 20 | 0.0789 | 0.0155 |
| hard_overlapping | 8000 | 32 | 1.003 | 0/3 | 3 (unreached 0) | 20 | 0.152 | 0.0279 |
| hard_overlapping | 32000 | 4 | 0.9989 | 3/3 | 1 (unreached 0) | 22 | 0.123 | 0.0101 |
| hard_overlapping | 32000 | 8 | 1 | 1/3 | 1.5 (unreached 0) | 19 | 0.191 | 0.0202 |
| hard_overlapping | 32000 | 16 | 1 | 1/3 | 2 (unreached 0) | 19 | 0.362 | 0.0402 |
| hard_overlapping | 32000 | 32 | 1 | 1/3 | 2.5 (unreached 0) | 19 | 0.872 | 0.0931 |
| hard_overlapping | 128000 | 4 | 1 | 2/3 | 1 (unreached 0) | 12 | 0.286 | 0.0371 |
| hard_overlapping | 128000 | 8 | 0.9995 | 3/3 | 1 (unreached 0) | 18 | 0.804 | 0.0532 |
| hard_overlapping | 128000 | 16 | 0.9987 | 3/3 | 1.5 (unreached 0) | 20 | 1.81 | 0.122 |
| hard_overlapping | 128000 | 32 | 0.9992 | 3/3 | 1.5 (unreached 0) | 17 | 3.68 | 0.225 |

## What the numbers mean

- b is the exponent in cost ~ n^b. Distance-evaluation exponents are hardware-free: b ~ 1 means a constant number of passes; b > 1 means passes-to-target grow with n. If b_lloyd > b_emeans by more than 2 SE, e-means' relative advantage grows with n (the card's 'large-scale phenomenon' reading); if less, it shrinks.
- Epochs/iterations to target are matched-init comparisons against Lloyd's OWN 25-iteration loss; Lloyd stopping early at that loss is the 'well-tuned Lloyd' the spec asks about.
- Wall time here is single-thread CPU numpy; e-means pays Python per-batch overhead, which dominates at small n.

## Limits

- Not the authors' code and not their scaling-law formulas (not in the card); results test an e-means-style solver built from the card's description with fixed heuristics, so a negative result may reflect the missing tuning rule rather than e-means itself - exactly the card's own T14 caveat.
- Synthetic Gaussian data, d=32, n <= 128k: far from the card's 10B-point / 16M-cluster regime.
- Epochs-to-target is resolved only to the budget grid; 3 seeds per cell.
