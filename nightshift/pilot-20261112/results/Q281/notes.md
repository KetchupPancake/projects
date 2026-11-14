# Q281 — Pre-run prediction value on Hydra run records

Implements spec item 4 (TOP10-TEST-SPECS-DRAFT.md) against card
C-meta-models-model-learning, reduced per CHECKS.md. Data:
`data/routing/job-usage-log.jsonl`.

## Mandatory limit

**The logs carry status and cost and NO quality labels.** Outcome in
this test is the logged `status` field (`ok` vs anything else:
ratelimit, refused, empty, error, timeout, truncated, auth, …).
`verified_correct` is present on 9381
rows and non-null on 0;
`verified_by` is non-null on 0. A higher
predicted P(ok) is a higher chance the logger wrote `status=ok`, not a
higher chance the answer was good. That limit is also in the headline.

## Data profile (computed, not assumed)

- 13003 records, times 2026-10-15T22:06:00-06:00 → 2026-11-09T17:10:59-06:00.
- Two shapes, mixed in one file:
  - job runs with `start`/`end`/`model` and quota deltas
    (`5h_used_before`/`after`, `wk_used_before`/`after`): 
    523 rows with `start`.
  - per-call rows with `task_type`/`provider`/`status`/`cost_usd`/`ts`
    (and a richer `row_kind=call` variant with route, latency,
    failure_type): 11767 rows with `status`,
    8673 with `task_type`.
- `cost_usd` is numeric on 9690 rows and
  **positive on only 762**. Almost all
  status-bearing rows are free-lane calls at $0. Paid-call rows
  (`job=hydra paid call`) carry dollars and **no status**.
- Status mix: {"auth": 103, "capacity": 35, "disabled": 1, "empty": 694, "error": 583, "fail": 8, "invalid_output": 22, "ok": 6552, "ratelimit": 2292, "refused": 857, "timeout": 357, "truncated": 263}.
- Task types: {"calibration": 90, "ceiling": 2242, "code_build": 4, "code_review": 146, "coding": 128, "construction_guide": 67, "long_doc": 46, "math": 83, "orchestration": 64, "private_data": 4, "research": 108, "research_synthesis": 1, "review": 2, "soak": 5688}.
- Top fields (n, nullish): [{"field": "model", "n": 12958, "nullish": 0}, {"field": "cost_usd", "n": 12767, "nullish": 3076}, {"field": "provider", "n": 12471, "nullish": 0}, {"field": "task_type", "n": 11786, "nullish": 3113}, {"field": "status", "n": 11767, "nullish": 0}, {"field": "job", "n": 10759, "nullish": 0}, {"field": "end", "n": 10460, "nullish": 1}, {"field": "ts", "n": 10268, "nullish": 0}, {"field": "route", "n": 9718, "nullish": 0}, {"field": "privacy_label", "n": 9639, "nullish": 24}, {"field": "row_kind", "n": 9497, "nullish": 0}, {"field": "tags_v", "n": 9381, "nullish": 0}].

## Method

Status-bearing rows with a `model` (11766) sorted by timestamp.
For each row the features are the running totals of prior rows with the
same `(model, task_type)`: `cost_so_far`, `calls_so_far`, plus dummy
codes for model (levels with ≥30 train rows; rest OTHER) and
task_type (missing → `unknown`). Chronological split: first
70% train (n=8236), last 30%
held-out (n=3530).

Two estimators, numpy only:

1. Least-squares linear probability (numpy.linalg.lstsq) — held-out R².
2. Hand-rolled logistic IRLS with L2=0.01 — held-out AUC.

Nested versions (intercept only; model+task_type only; full) show how
much `cost_so_far` and `calls_so_far` add on top of the categoricals.
Continuous features are z-scored on train so logistic/OLS coefficients
on those two columns are per training SD.

Routing/config value (spec): among models with ≥30 train and ≥50
later-slice rows, pick the one with the highest mean training
predicted P(ok) and compare its later-slice ok-rate to the mix
actually used. Per-task_type picks are reported only when the chosen
model has ≥30 later-slice rows of that type. Net benefit sign is the
sign of the model-level ok-rate delta, minus collection cost = sum of
training-slice `cost_usd` (0.013261 USD).

## What the numbers mean

- Held-out logistic AUC **0.6899** vs categoricals-only
  **0.6739** vs intercept-only
  **0.5**. Intercept-only should sit at 0.5;
  the jump from intercept to categoricals is the model/task_type base
  rate. The increment from categoricals to full is the value of cost
  so far and calls so far.
- Held-out OLS R² **0.0117** vs categoricals-only
  **0.0083**.
- Effect of cost so far: -0.1299 log-odds per train SD
  (train SD 0.000073 USD). Predicted P(ok) at mean features
  0.54 vs +1 SD cost
  0.5077.
- Effect of calls so far: 0.0324 log-odds per train SD
  (SD=222.4421). Predicted P(ok) at +1 SD calls
  0.5481.
- Later-slice ok-rate, actual mix: **0.5929**.
  Recommended model `nvidia/Qwen3.8-27B-NVFP4` (n_test=160):
  **0.75**. Delta vs full mix:
  **0.1571**. Vs eligible-model mix:
  **0.1572**. Top-3 later ok-rate
  0.7404 vs bottom-3 0.6776.
  Net-benefit sign: **positive**. Collection cost
  0.013261 USD.
- Train ok-rate 0.5413, test ok-rate 0.5929
  (base rates can shift across the split; that is why intercept-only
  AUC on a shifted test set can differ slightly from 0.5 when scores
  are constant — here intercept-only uses a constant, so AUC is 0.5
  whenever both classes appear).

## Limits

- Status is not quality. Soak and ceiling rows dominate; `ok` there
  means the provider returned a completion, not that a judge scored
  the answer. Do not read the AUC as "the predictor finds good models".
- `cost_so_far` is train SD 0.000073 USD. Paid dollars live on a different row
  shape with no status, so this regression cannot speak to dollar
  cost-awareness. That is a log-schema gap, not a modelling choice.
- Routing delta is observational. Later-slice tasks were not randomly
  assigned to models; the recommended model's later ok-rate may mix
  selection with model skill. Chronological shift: ceiling is
  27.2% of train and
  0.0% of test; soak is
  31.5% of train and
  87.7% of test. That is why train
  R²/AUC overstate held-out fit.
- The spec asked for net benefit in outcome/cost minus collection
  cost. Dollars are not on the status rows, so the sign is reported
  on the ok-rate delta instead of a dollar net. Closest faithful
  reading; stated as an assumption.
- Card C-meta-models-model-learning is not staged under cards/; the
  protocol follows the spec text plus CHECKS.md's reduced outcome.
