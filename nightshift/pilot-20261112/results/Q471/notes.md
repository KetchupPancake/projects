# Q471 - e-means vs k-means on staged corpus text embeddings (independent replication for card 162)

Status: **done** | runtime 6.87s | 2026-11-12T23:32:20-06:00 -> 2026-11-12T23:32:26-06:00
Spec: TOP10-TEST-SPECS-DRAFT.md item 10, as framed by the run brief. Card: `cards/C-e-means-outperforming-k-means-muse-20261111.md`.

## Verdict: **weakens**

- 0/6 text cells have median e-means@2.5ep loss <= Lloyd-25 loss (f = 0.00; thresholds 2/3 stands, 1/3 weakens)
- magnitude: per-cell median e-means@2.5ep / Lloyd-25 loss ranges 1.0022-1.0092 (i.e. +0.22% to +0.92%)
- scope: n <= 648 TF-IDF/SVD text with a heuristic batch/decay schedule (authors' scaling-law formulas not in the card); this bears on the small-n, off-family question only, not on the card's large-scale GPU claims

## Method

Embedded 648 staged take-aways with numpy TF-IDF + truncated SVD (64 dims, unit rows). Grid k in [4, 8, 12] x n in [324, 648] x 10 seeds: plain Lloyd (25 iters) and an e-means-style EMA mini-batch solver from the same random init, e-means at epoch budgets [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0], plus k-means++ Lloyd. Per run: inertia, wall time, epochs/iterations to Lloyd-25 loss, exact silhouette. One synthetic Gaussian mixture with known labels (5 seeds) scored by hand-computed ARI. Verdict by a pre-stated rule on the fraction of text cells where e-means at 2.5 epochs matches or beats Lloyd-25 loss.

Embedding: vocab 1989 terms, SVD energy retained 0.2551, 0 docs with no vocabulary terms, embed time 1.374s.

## Assumptions

- Corpus: the 648 take-away strings in data/takeaways-full.json (leading theme tag like 'T6:' stripped). The staged question set is not used - the brief names the take-aways file.
- Embedding: TF-IDF (tokens [a-z][a-z0-9-]+, small stop list, min_df=2, max_df=50%, sublinear tf, smoothed idf, l2) then exact SVD truncated to 64 dims, rows re-normalised to unit length. A neural embedder was not attempted (no model downloads in the run room; numpy only).
- Sample sizes: n = 324 (random subset per seed, drawn from the full embedded corpus) and n = 648 (full). TF-IDF/SVD is fitted once on all 648 texts.
- e-means-style solver per the card's listed components; batch size b = min(n, max(4k, round(sqrt(n*k)))) and the step-size schedule (cosine 0.5 -> 1/(batches per epoch)) are this script's heuristics because the card does not print the authors' scaling-law formulas. Donor-split detail of revival is not in the card (split along 1% of the offset to a donor batch point).
- Baseline: Lloyd 25 iterations (or fixed point) from the same random init as e-means; k-means++ Lloyd as a stronger loss reference. Target-reached tolerance 0.001 for both solvers; the card-claim check is strict (<=) at 2.5 epochs, the largest budget grid point within the card's 2.6.
- Quality proxies: inertia (sum of squared Euclidean distances on unit-normalised embeddings) and exact silhouette over all points (n <= 648 makes the full computation cheap, so no sampling). ARI is computed from the contingency table on a synthetic mixture with known labels.
- Synthetic ground-truth set: n=2000, d=64, 8 Gaussian components, centres N(0, 0.5^2), unit noise, uniform labels; k = k_true.
- Runtime = single-thread numpy wall time of algorithm steps only (evaluation passes untimed). At these n, timings are microseconds-to-milliseconds and overhead-dominated; they are reported, not used in the verdict.
- Verdict rule was fixed in code before the run (see verdict_reasons).

## Results - text grid (medians over seeds)

| n | k | seeds | em2.5/L25 loss | em2.5 beats L25 | em2.5 beats L++ | em epochs->target | Lloyd iters->target | Lloyd s->target | em s->target | sil L25 | sil L++ | sil em2.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 324 | 4 | 10 | 1.0045 | 1/10 | 1/10 | 2.5 (unreached 0) | 6.5 | 0.000887 | 0.00105 | 0.0182 | 0.019 | 0.0165 |
| 324 | 8 | 10 | 1.0046 | 3/10 | 1/10 | 2 (unreached 0) | 6.5 | 0.00143 | 0.000938 | 0.0231 | 0.0258 | 0.021 |
| 324 | 12 | 10 | 1.0085 | 0/10 | 2/10 | 2 (unreached 0) | 8 | 0.00242 | 0.00106 | 0.0293 | 0.0311 | 0.0264 |
| 648 | 4 | 10 | 1.0022 | 2/10 | 2/10 | 3 (unreached 1) | 10.5 | 0.00243 | 0.00197 | 0.0178 | 0.0176 | 0.0164 |
| 648 | 8 | 10 | 1.0092 | 2/10 | 3/10 | 3 (unreached 2) | 17.5 | 0.00697 | 0.0023 | 0.0275 | 0.0251 | 0.0232 |
| 648 | 12 | 10 | 1.0086 | 1/10 | 2/10 | 3 (unreached 0) | 17.5 | 0.00993 | 0.00266 | 0.0337 | 0.0321 | 0.0307 |

## Card prediction vs measured

- Card (authors' numbers): below Lloyd's 25-epoch loss within 1.4-2.6 epochs.
- Measured on text: 57/60 runs reached Lloyd-25 loss (within 0.001) by 5 epochs, 28 by 2.5 epochs; median epochs where reached = 3.0.
- Strictly below Lloyd-25 at 2.5 epochs in 9/60 runs; below k-means++ Lloyd in 11/60.

## Synthetic ground truth (ARI)

Config {'n': 2000, 'd': 64, 'k_true': 8, 'center_sd': 0.5, 'seeds': [0, 1, 2, 3, 4]}; 5 seeds. Median ARI: lloyd25 = 0.9531, lloydpp = 0.932, em1.0 = 0.9063, em2.5 = 0.9498. Median em2.5/L25 loss = 1.0017; e-means@2.5 strictly below Lloyd-25 in 2/5 seeds.

## What the numbers mean

- em2.5/L25 < 1 means the e-means-style solver, given 2.5 passes, found lower inertia than 25 Lloyd passes from the same start - the card's central claim, in its own units (epochs, not GPU seconds).
- Silhouette and ARI check that lower inertia is not bought with worse partitions.
- All text-grid median silhouettes are below 0.1 (max 0.034): the take-away embeddings have weak cluster structure, so the solvers are choosing among many near-equivalent partitions and sub-1% inertia gaps carry little practical meaning.
- Wall times at n <= 648 are tiny and dominated by Python overhead; they are not evidence about the card's 10-45x GPU speedups either way.

## Limits

- Not the authors' implementation or formulas: an e-means-style solver from the card's description with fixed heuristics. A shortfall can come from the missing tuning rule (the card's own T14 caveat), not from e-means as published.
- n <= 648 sparse-text embeddings in 64 dims: this is a small-scale off-family check, not 'Academy scale' in the card's sense of a large index build; the spec's scaling-formula fit error is not computable (formulas not in card).
- TF-IDF/SVD, not a neural embedder; the geometry of neural text embeddings may differ.
